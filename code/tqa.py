""" Utility classes and functions related to MACT (NAACL 2025). 

Copyright (c) 2025 Robert Bosch GmbH 


This program is free software: you can redistribute it and/or modify 

it under the terms of the GNU Affero General Public License as published 

by the Free Software Foundation, either version 3 of the License, or 

(at your option) any later version. 

This program is distributed in the hope that it will be useful, 

but WITHOUT ANY WARRANTY; without even the implied warranty of 

MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 

GNU Affero General Public License for more details. 

You should have received a copy of the GNU Affero General Public License 

along with this program.  If not, see <https://www.gnu.org/licenses/>. 

"""


import traceback
import json
import argparse
import sglang as sgl
from agents import ReactAgent
from sglang.lang.chat_template import (ChatTemplate, get_chat_template,
                                       register_chat_template)
from utils import summarize_react_trial, table2df
from utils import get_databench_table
from config import llm_config


def write_to_file(path, agent, idx, new_table_dataset, given_plan):
    with open(path, "a") as f:
        agent.run(given_plan)
        pred_answer = agent.answer
        item = new_table_dataset[idx]
        item["pred_answer"] = pred_answer
        item["history"] = agent.scratchpad
        item["pred_answer_all"] = agent.pre_ans_all
        # item["code_log"] = agent.generated_code
        # item["plan_log"] = agent.generated_plan
        f.write(json.dumps(item)+"\n")
    return agent

# ===================================================


def load_codellama_template(endpoint2):
    codellama_template = ChatTemplate(
        name="codellama",
        default_system_prompt=(
            "You are an intelligent programming assistant."
        ),
        role_prefix_and_suffix={
            "system": ("### System Promopt\n", "\n"),
            "user": ("### User Message\n", "\n"),
            "assistant": ("### Assistant", ""),
        }
    )
    register_chat_template(codellama_template)
    endpoint2.chat_template = get_chat_template("codellama")


def main(args):
    codeagent_endpoint = None
    
    # Simplified model setup - no need for separate vLLM/transformers loading
    # The unified LLM interface handles model routing automatically
    model = None  # Not needed with unified approach
    tokenizer = None  # Not needed with unified approach
    
    # SGLang endpoint setup (if needed for batch processing)
    if not llm_config.is_gpt_model(args.code_model_name):
        codeagent_endpoint = sgl.RuntimeEndpoint(
            f"http://localhost:{args.code_endpoint}")
        if "codellama" in args.code_model_name.lower():
            load_codellama_template(codeagent_endpoint)

    with open(args.dataset_path, "r") as f:
        table_dataset = [json.loads(line) for line in f]

    trial = 0
    agent_cls = ReactAgent
    agents = [agent_cls(question=row["question"] if "question" in list(row.keys()) else row["statement"],
              table=get_databench_table(args.table_dir, row["dataset"])[
        0] if args.task == "databench" else row["table_text"],
        table_df=table2df(get_databench_table(args.table_dir, row["dataset"])[
            1]) if args.task == "databench" else table2df(row["table_text"]),
        df_path=get_databench_table(args.table_dir, row["dataset"])[
        2] if args.task == "databench" else "",
        context=row["text"] if "text" in list(row.keys()) else "",
        key=row["answer"] if "answer" in list(row.keys()) else "none",
        answer="",
        max_steps=args.max_step,
        max_actual_steps=args.max_actual_step,
        plan_model_name=args.plan_model_name,
        code_model_name=args.code_model_name,
        model=model,  # This can be None with unified approach
        tokenizer=tokenizer,  # This can be None with unified approach
        task=args.task,
        codeagent_endpoint=codeagent_endpoint,
        as_reward=args.as_reward,
        plan_sample=args.plan_sample,
        code_sample=args.code_sample,
        use_pre_answer=args.use_pre_answer,
        answer_aggrement=args.answer_aggregate,
        direct_reasoning=args.direct_reasoning,
        long_table_op=args.long_table_op,
        debugging=args.debugging,
        code_as_observation=args.code_as_observation,
        without_tool=args.without_tool) for _, row in enumerate(table_dataset)]
    if args.debugging:
        agents = agents[0:1]
        for idx, agent in enumerate([a for a in agents]):
            print(idx)
            print(agent.question)
            print(agent.table_string)
            agent.run()
            print(f'Answer: {agent.key}, Pred: {agent.answer}')
            print(agent.scratchpad)
            trial += 1
            correct, incorrect, halted = summarize_react_trial(agents)
            print(f'Finished Trial {trial}, Correct: {len(correct)}, \
                    Incorrect: {len(incorrect)}, Halted: {len(halted)}')
    else:
        finished_agents = []
        plan_model_name = args.plan_model_name.split("/")[-1].strip()
        code_model_name = args.code_model_name.split("/")[-1].strip()
        output_path = f"{args.task}_{plan_model_name}_{code_model_name}_{args.as_reward}_{args.plan_sample}_{args.code_sample}_direct_{args.direct_reasoning}_{args.answer_aggregate}.json"
        for idx, agent in enumerate([a for a in agents]):
            try:
                finished_agent = write_to_file(
                    output_path, agent, idx, table_dataset, given_plan=None)
                finished_agents.append(finished_agent)
                trial += 1
                correct, incorrect, halted = summarize_react_trial(
                    finished_agents)
                print(
                    f'Finished Trial {trial}, Correct: {len(correct)}, Incorrect: {len(incorrect)}, Halted: {len(halted)}')
            except Exception as e:
                print(traceback.format_exc())
                break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan_model_name',
                        default="", help="name of the planning model.")
    parser.add_argument('--code_model_name',
                        default="", help="name of the coding model.")
    parser.add_argument('--cache_dir', default="",
                        help="cache dir to load a model from.")
    parser.add_argument('--model_path', type=str,
                        default="", help="model path to the planning model.")
    parser.add_argument('--dataset_path', type=str,
                        default="../datasets/wtq.jsonl", help="dataset path.")
    parser.add_argument('--table_dir', type=str,
                        default="../datasets/databench/data", help="databench table directory")
    parser.add_argument('--max_step', type=int, default=6,
                        help="maximum number for valid iterations.")
    parser.add_argument('--max_actual_step', type=int, default=6,
                        help="maximum number for all iterations.")
    parser.add_argument('--task', type=str, default="wtq",
                        choices=["wtq", "crt", "tat", "scitab", "databench"])
    parser.add_argument('--as_reward', type=str, default="consistency",
                        choices=["consistency", "llm", "logp", "rollout", "combined"])
    parser.add_argument('--long_table_op', type=str, default="ignore",
                        choices=["code-agent", "ignore", "short-table"],
                        help="methods to shorten long table. default passing the whole table.")
    parser.add_argument('--plan_sample', type=int, default=5,
                        help="number of actions sampled from a planning model.")
    parser.add_argument('--code_sample', type=int, default=5,
                        help="numbers of trails for generating codes to address an action.")
    parser.add_argument('--use_pre_answer', type=bool, default=True,
                        help="whether use answers from the first iteration as final answers.")
    parser.add_argument('--answer_aggregate', type=float, default=1.,
                        help="agreement threshold for answer selection of use_pre_answer.")
    parser.add_argument('--direct_reasoning', action='store_true',
                        help="whether to use cot and symbolic reasoning directly or not.")
    parser.add_argument('--without_tool', action='store_true')
    parser.add_argument('--code_endpoint', default="11039",
                        help="coding agent port.")
    parser.add_argument('--debugging', action='store_true')
    parser.add_argument('--code_as_observation', action='store_true',
                        help="only use code as the final observations or not.")
    args = parser.parse_args()
    main(args)
