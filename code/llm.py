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

from transformers import AutoModelForCausalLM, AutoTokenizer
# from mistral_common.protocol.instruct.request import ChatCompletionRequest
# from mistral_common.protocol.instruct.messages import UserMessage
# from mistral_common.tokens.tokenizers.mistral import MistralTokenizer
# from mistral_inference.generate import generate
# from mistral_inference.transformer import Transformer
import random
from typing import Union, Literal
from vllm import SamplingParams
import torch
import transformers
import math

transformers.set_seed(42)
random.seed(42)


# def mistral_inference(model, tokenizer, prompts):
#     results = []
#     for prompt in prompts:
#         completion_request = ChatCompletionRequest(
#             messages=[UserMessage(content=prompt["content"])])

#         tokens = tokenizer.encode_chat_completion(completion_request).tokens

#         out_tokens, _ = generate([tokens], model, max_tokens=2000, temperature=0,
#                                  eos_id=tokenizer.instruct_tokenizer.tokenizer.eos_id)
#         result = tokenizer.decode(out_tokens[0])
#         results.append(result)

#     return results


class OpenSourceLLM:
    def __init__(self, model_name, model, vllm, tokenizer):
        self.model_name = model_name
        self.tokenizer = tokenizer
        self.model = model
        self.vllm = vllm
        self.pad_ids = tokenizer.eos_token_id if "mistral" not in model_name.lower() else None
        if self.pad_ids:
            self.tokenizer.pad_token_id = self.pad_ids

    def get_log_scores(self, outputs):
        # based on vllm returned log prob
        # log p is only calculated on the desired sequences but not all generated!!!
        ids = self.tokenizer.encode("Observation ")[0]
        sequence_probs = []
        for item in outputs[0].outputs:
            try:
                ending_id = item.token_ids.index(ids)
                target_probs = [list(probs.values())[
                    0].logprob for probs in item.logprobs[:ending_id]]
            except:
                # hit the finish token
                target_probs = [list(probs.values())[
                    0].logprob for probs in item.logprobs]
            try:
                sequence_prob = math.exp(sum(target_probs)/len(target_probs))
            except:
                sequence_prob = 0
            sequence_probs.append(sequence_prob)
        return sequence_probs

    def get_sampled_scores(self, generate_output_sample, input_length):
        # no vllm needed
        # https://colab.research.google.com/drive/1vLmUfqYdKVo1z2Ztv2V2sQ29nDCYNbFK?usp=sharing#scrollTo=GKpqjMnnnJhK
        sequence_prob = []
        num_sequences = len(generate_output_sample.sequences)

        for seq_index in range(num_sequences):
            probs_sample = []
            target_sequence = generate_output_sample.sequences[seq_index, input_length:]
            pad_end = torch.where(target_sequence != torch.tensor(self.pad_ids))[
                0][-1].tolist() + 1
            target_sequence = target_sequence[:pad_end]

            for i, ids in enumerate(target_sequence):
                logits = generate_output_sample.scores[i][seq_index, :].reshape(
                    (1, -1))
                logprobs = torch.nn.functional.log_softmax(logits, dim=1)
                probs_sample.append(logprobs[0][ids].tolist())
            sequence_prob.append(math.exp(sum(probs_sample)/len(probs_sample)))
        return sequence_prob

    def __call__(self, prompt: str, num_return_sequences: int, return_prob: bool):
        # if "mistral" in self.model_name.lower():
        #     # specifically for mistral nemo model
        #     messages = [{"role": "user", "content": prompt}]
        #     decoded = mistral_inference(self.model, self.tokenizer, messages)

        if "qwen" in self.model_name.lower() or "phi" in self.model_name.lower() or "mistral" in self.model_name.lower():
            decoded = []
            if return_prob:
                sampling_params = SamplingParams(
                    max_tokens=2000, temperature=0.6, top_p=0.95, n=num_return_sequences, logprobs=1)
            else:
                sampling_params = SamplingParams(
                    max_tokens=2000, temperature=0.6, top_p=0.95, n=num_return_sequences)
            outputs = self.vllm.generate([prompt], sampling_params)
            decoded = [item.text for item in outputs[0].outputs]
            if return_prob:
                scores = self.get_log_scores(outputs)
                # return scores as a list
                decoded.append(scores)
        elif "llama" in self.model_name.lower():
            msg = self.tokenizer.apply_chat_template(
                prompt, tokenize=False)
            sampling_params = SamplingParams(
                max_tokens=2000, temperature=0.6, top_p=0.95, n=num_return_sequences)
            outputs = self.vllm.generate([msg], sampling_params)
            decoded = [item.text for item in outputs[0].outputs]

        return decoded

    def encode(self, prompt: str):
        # if "mistral" in self.model_name.lower():
        #     messages = [{"role": "user", "content": prompt}]
        #     encodeds = self.tokenizer.apply_chat_template(
        #         messages, return_tensors="pt")  # (1,len(input_ids))

        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        encodeds = self.tokenizer([text], return_tensors="pt").input_ids

        return len(encodeds[0])
