""" Multi-table Question Answering using MACT framework for MMQA dataset.

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
from agents import ReactAgent
from utils import summarize_react_trial, table2df, table_linear
from config import llm_config


def process_mmqa_tables(tables_data):
    """Convert MMQA tables data to unified format."""
    combined_tables = []
    table_names = []
    
    for table_info in tables_data:
        table_name = table_info.get('table_name', 'Unknown')
        table_names.append(table_name)
        
        # Extract table content
        columns = table_info['table_columns']
        content = table_info['table_content']
        
        # Create table in list format
        table_rows = [columns] + content
        combined_tables.append({
            'name': table_name,
            'data': table_rows,
            'linear': table_linear(table_rows, num_row=None)
        })
    
    return combined_tables, table_names


def create_mmqa_context(item):
    """Create context string from MMQA item metadata."""
    context_parts = []
    
    if 'table_names' in item:
        context_parts.append(f"Tables: {', '.join(item['table_names'])}")
    
    if 'foreign_keys' in item and item['foreign_keys']:
        context_parts.append(f"Foreign Keys: {', '.join(item['foreign_keys'])}")
        
    if 'primary_keys' in item and item['primary_keys']:
        context_parts.append(f"Primary Keys: {', '.join(item['primary_keys'])}")
    
    return " | ".join(context_parts)


def combine_tables_for_qa(combined_tables):
    """Combine multiple tables into a single representation for QA."""
    if len(combined_tables) == 1:
        return combined_tables[0]['linear'], combined_tables[0]['data']
    
    # For multi-table cases, create a combined representation
    combined_text = "Multi-table dataset:\n\n"
    all_table_data = []
    
    for i, table in enumerate(combined_tables):
        combined_text += f"Table {i+1} ({table['name']}):\n"
        combined_text += table['linear'] + "\n\n"
        all_table_data.extend(table['data'])
    
    return combined_text.strip(), all_table_data


def write_to_file(path, agent, idx, dataset_item):
    """Write results to output file."""
    with open(path, "a") as f:
        agent.run()
        pred_answer = agent.answer
        
        # Create output item
        result_item = {
            "id_": dataset_item.get("id_", idx),
            "Question": dataset_item["Question"],
            "SQL": dataset_item.get("SQL", ""),
            "table_names": dataset_item.get("table_names", []),
            "answer": dataset_item["answer"],
            "pred_answer": pred_answer,
            "history": agent.scratchpad,
            "pred_answer_all": agent.pre_ans_all if hasattr(agent, 'pre_ans_all') else []
        }
        
        f.write(json.dumps(result_item) + "\n")
    
    return agent


def main(args):
    print(f"Loading MMQA dataset from: {args.dataset_path}")
    
    # Load MMQA dataset
    with open(args.dataset_path, "r") as f:
        dataset = json.load(f)
    
    if not isinstance(dataset, list):
        print("Error: Expected MMQA dataset to be a list of items")
        return
    
    print(f"Loaded {len(dataset)} items from MMQA dataset")
    
    # Process dataset and create agents
    agents = []
    processed_dataset = []
    
    for idx, item in enumerate(dataset):
        try:
            # Process tables
            combined_tables, table_names = process_mmqa_tables(item['tables'])
            
            # Create unified table representation
            table_string, table_data = combine_tables_for_qa(combined_tables)
            table_df_code = table2df(table_data) if table_data else ""
            
            # Create context
            context = create_mmqa_context(item)
            
            # Get answer (handle different answer formats)
            answer = item.get('answer', '')
            if isinstance(answer, list):
                answer = answer[0] if answer else ''
            
            # Create agent
            agent = ReactAgent(
                question=item['Question'],
                table=table_data if table_data else [[]],
                table_df=table_df_code,
                df_path="",
                context=context,
                key=str(answer),
                answer="",
                max_steps=args.max_step,
                max_actual_steps=args.max_actual_step,
                plan_model_name=args.plan_model_name,
                code_model_name=args.code_model_name,
                model=None,
                tokenizer=None,
                task="mmqa",  # New task type
                codeagent_endpoint=None,
                as_reward=args.as_reward,
                plan_sample=args.plan_sample,
                code_sample=args.code_sample,
                use_pre_answer=args.use_pre_answer,
                answer_aggrement=args.answer_aggregate,
                direct_reasoning=args.direct_reasoning,
                long_table_op=args.long_table_op,
                debugging=args.debugging,
                code_as_observation=args.code_as_observation,
                without_tool=args.without_tool
            )
            
            agents.append(agent)
            
            # Store processed item for output
            processed_item = item.copy()
            processed_item['table_string'] = table_string
            processed_dataset.append(processed_item)
            
        except Exception as e:
            print(f"Error processing item {idx}: {e}")
            if args.debugging:
                print(traceback.format_exc())
            continue
    
    print(f"Created {len(agents)} agents successfully")
    
    if args.debugging:
        # Debug mode - process only first item
        agents = agents[:1]
        processed_dataset = processed_dataset[:1]
        
        for idx, agent in enumerate(agents):
            print(f"\n=== Debug Item {idx} ===")
            print(f"Question: {agent.question}")
            print(f"Answer: {agent.key}")
            print(f"Table preview:\n{agent.table_string[:500]}...")
            
            agent.run()
            print(f'Predicted: {agent.answer}')
            print(f'Ground Truth: {agent.key}')
            print(f"Scratchpad:\n{agent.scratchpad}")
            
            # Check correctness
            correct, incorrect, halted = summarize_react_trial([agent])
            print(f'Results: Correct: {len(correct)}, Incorrect: {len(incorrect)}, Halted: {len(halted)}')
    
    else:
        # Normal mode - process all items
        finished_agents = []
        
        # Create output filename
        plan_model_name = args.plan_model_name.split("/")[-1].strip()
        code_model_name = args.code_model_name.split("/")[-1].strip()
        output_path = f"mmqa_{plan_model_name}_{code_model_name}_{args.as_reward}_{args.plan_sample}_{args.code_sample}_direct_{args.direct_reasoning}_{args.answer_aggregate}.jsonl"
        
        print(f"Output will be saved to: {output_path}")
        
        # Clear output file
        with open(output_path, "w") as f:
            pass
        
        for idx, (agent, dataset_item) in enumerate(zip(agents, processed_dataset)):
            try:
                print(f"\nProcessing item {idx + 1}/{len(agents)}")
                print(f"Question: {agent.question[:100]}...")
                
                finished_agent = write_to_file(output_path, agent, idx, dataset_item)
                finished_agents.append(finished_agent)
                
                # Calculate running statistics
                correct, incorrect, halted = summarize_react_trial(finished_agents)
                accuracy = len(correct) / len(finished_agents) if finished_agents else 0
                
                print(f'Progress: {idx + 1}/{len(agents)} | '
                      f'Correct: {len(correct)} | '
                      f'Incorrect: {len(incorrect)} | '
                      f'Halted: {len(halted)} | '
                      f'Accuracy: {accuracy:.3f}')
                
            except Exception as e:
                print(f"Error processing item {idx}: {e}")
                if args.debugging:
                    print(traceback.format_exc())
                continue
        
        # Final statistics
        if finished_agents:
            correct, incorrect, halted = summarize_react_trial(finished_agents)
            final_accuracy = len(correct) / len(finished_agents)
            
            print(f"\n=== Final Results ===")
            print(f"Total processed: {len(finished_agents)}")
            print(f"Correct: {len(correct)}")
            print(f"Incorrect: {len(incorrect)}")
            print(f"Halted: {len(halted)}")
            print(f"Final Accuracy: {final_accuracy:.3f}")
            print(f"Results saved to: {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="MACT framework for MMQA dataset")
    
    # Model arguments
    parser.add_argument('--plan_model_name', default="gpt-3.5-turbo", 
                        help="Name of the planning model")
    parser.add_argument('--code_model_name', default="gpt-3.5-turbo", 
                        help="Name of the coding model")
    
    # Data arguments
    parser.add_argument('--dataset_path', type=str, 
                        default="../cs8903_benchmark/datasets/mmqa_samples.json",
                        help="Path to MMQA dataset JSON file")
    
    # Agent configuration
    parser.add_argument('--max_step', type=int, default=6,
                        help="Maximum number of valid iterations")
    parser.add_argument('--max_actual_step', type=int, default=6,
                        help="Maximum number of all iterations")
    
    # Sampling and reward
    parser.add_argument('--as_reward', type=str, default="consistency",
                        choices=["consistency", "llm", "logp", "rollout", "combined"],
                        help="Reward mechanism for action selection")
    parser.add_argument('--plan_sample', type=int, default=5,
                        help="Number of actions sampled from planning model")
    parser.add_argument('--code_sample', type=int, default=5,
                        help="Number of trials for code generation")
    
    # Answer configuration
    parser.add_argument('--use_pre_answer', type=bool, default=True,
                        help="Whether to use answers from first iteration")
    parser.add_argument('--answer_aggregate', type=float, default=1.0,
                        help="Agreement threshold for answer selection")
    
    # Mode options
    parser.add_argument('--direct_reasoning', action='store_true',
                        help="Use CoT and symbolic reasoning directly")
    parser.add_argument('--without_tool', action='store_true',
                        help="Disable tool usage")
    parser.add_argument('--debugging', action='store_true',
                        help="Enable debugging mode (process only first item)")
    parser.add_argument('--code_as_observation', action='store_true',
                        help="Use code as final observations only")
    
    # Table handling
    parser.add_argument('--long_table_op', type=str, default="ignore",
                        choices=["code-agent", "ignore", "short-table"],
                        help="Method to handle long tables")
    
    args = parser.parse_args()
    
    print("MACT Framework for MMQA Dataset")
    print("=" * 40)
    print(f"Plan Model: {args.plan_model_name}")
    print(f"Code Model: {args.code_model_name}")
    print(f"Dataset: {args.dataset_path}")
    print(f"Reward: {args.as_reward}")
    print(f"Plan Samples: {args.plan_sample}")
    print(f"Code Samples: {args.code_sample}")
    print(f"Direct Reasoning: {args.direct_reasoning}")
    print(f"Debugging: {args.debugging}")
    print("=" * 40)
    
    main(args)