import argparse
import ast
import random
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Lock

import openai

from generate_clang_mutations import get_operator_descriptions_for_ai
from meta import *
from util import *

SEPARATOR_EXPLANATION_START = '<EXPLANATION>'
SEPARATOR_EXPLANATION_END = '</EXPLANATION>'
SEPARATOR_CODE_START = '<CODE>'
SEPARATOR_CODE_END = '</CODE>'

error_counter = 0


# generates mutated program by using chat-gpt
def generate_ai_mutations(program_path, apikey_path, ai_count, num_selected_lines, interesting_lines, ai_16k, index):
    meta_set_n(index + ai_count)

    # Read the api key and organization
    with open(apikey_path, 'r') as file:
        data = yaml.safe_load(file)
    organisation = data.get('organisation')
    api_key = data.get('api-key')

    # Authenticate
    openai.organization = organisation
    openai.api_key = api_key

    # Get interesting lines
    with open(program_path, "r") as file:
        max_line = len(file.readlines())
    if max_line < num_selected_lines:
        num_selected_lines = max_line
    interesting_lines = validate_interesting_lines(interesting_lines, program_path)
    interesting_lines = _reformat_interesting_lines(num_selected_lines, interesting_lines, max_line)

    print_separator()
    interesting_lines_string = 'Start lines are randomly chosen from all lines.' if interesting_lines == [] else f' Start lines are randomly chosen from {interesting_lines}.'
    print(
        f'[AI] Start making {ai_count} requests with AI. {AI_WORKERS} are executed in parallel. {num_selected_lines} from {max_line} lines will be selected. {interesting_lines_string}')

    # Start executing multiple requests in parallel
    file_lock = Lock()
    with ThreadPoolExecutor(max_workers=AI_WORKERS) as executor:
        for i in range(ai_count):
            executor.submit(_iterative_mutation_generation, program_path, interesting_lines, ai_16k,
                            num_selected_lines, max_line, index + i + 1, file_lock)

    print_separator()
    print('Check if all AI requests finished successfully...')
    print(f'{COLOR_GREEN}Finished all requests.{COLOR_RESET}' + (
        f'{COLOR_RED} {error_counter} failed with an exception.{COLOR_RESET}' if error_counter > 0 else ''))

    return index + ai_count


# Call for each mutation
def _iterative_mutation_generation(program_path, interesting_lines, ai_16k, num_selected_lines, max_line,
                                   index, lock):
    try:
        time.sleep((index * 50) / 1000)  # Sleep depending on index to print the start messages in the right order
        new_path = make_program_copy(program_path, index)
        (response, selected_lines, prompt_tokens, completion_tokens) = _apply_mutation(new_path, interesting_lines, ai_16k, num_selected_lines, max_line, index)
        _update_meta(selected_lines, remove_ansi_escape_sequences(response), prompt_tokens, completion_tokens, index, lock)
    except Exception as e:
        print(f"{COLOR_RED}[{index}] Error for request {index}:{COLOR_RESET} {e}")
        _update_meta(None, '', 0, 0, index, lock, exception=e)
    return index


# Makes a gpt request and places the result in the program
def _apply_mutation(new_path, interesting_lines, ai_16k, num_selected_lines, max_line, index):
    # Get the initial lines
    with open(new_path, "r") as file:
        lines = file.readlines()

    # Get code snippet
    selected_lines = _select_lines(interesting_lines, num_selected_lines, max_line)
    snippet = ''
    for i in selected_lines:
        snippet += lines[i]

    print(f"[{index}][{GenerateType.AI.value}][REQUEST] Make request for lines [{selected_lines.start}, {selected_lines.stop}]. This may take a few seconds...")

    # Get response from gpt
    (response, prompt_tokens, completion_tokens) = _make_gpt_request(snippet, ai_16k)

    # Extract Explanation
    explanation_start = response.find(SEPARATOR_EXPLANATION_START) + len(SEPARATOR_EXPLANATION_START)
    explanation_end = response.find(SEPARATOR_EXPLANATION_END)
    explanation = response[explanation_start:explanation_end].strip()

    # Extract Code lines
    code_start = response.find(SEPARATOR_CODE_START) + len(SEPARATOR_CODE_START)
    code_end = response.find(SEPARATOR_CODE_END)
    code = response[code_start:code_end].strip()
    new_code_lines = code.splitlines()
    new_code_lines = [line for line in new_code_lines if line != '```' and line != '```c' and line != '``']

    # Comment out the initial lines
    for i in selected_lines:
        lines[i] = '// ' + lines[i]

    # Add start marker
    lines.insert(selected_lines[0], f'//[AI][START] {explanation.replace("/n", "")}\n')

    # Insert new lines of code
    for i, new_line in enumerate(new_code_lines, start=selected_lines[0] + 1):
        lines.insert(i, new_line + '\n')

    # Add end marker
    lines.insert(selected_lines[0] + len(new_code_lines) + 1, '//[AI][END]\n')

    # Write the updated lines back to the file
    with open(new_path, "w") as file:
        file.writelines(lines)

    explanation_lines = explanation.splitlines()
    limited_explanation = "\n".join(explanation_lines[:4])
    print(f'{COLOR_GREEN}[{index}] Finished request with {prompt_tokens} prompt tokens and {completion_tokens} completion tokens ({prompt_tokens + completion_tokens} total):{COLOR_RESET} {limited_explanation}')

    return response, selected_lines, prompt_tokens, completion_tokens


def _update_meta(selected_lines, response, prompt_tokens, completion_tokens, index, lock, exception=None):
    lock.acquire()
    global error_counter   
    try:
        if selected_lines is not None:
            lines = [selected_lines.start, selected_lines.stop]
        else:
            lines = []
        if response is None:
            response = ''
        meta_create_index(index, GenerateType.AI.value, response, lines)
        if prompt_tokens != 0 or completion_tokens != 0:
            meta_add_ai_tokens(prompt_tokens, completion_tokens, index)
        if exception is not None:
            error_counter += 1
            meta_exception(index, META_EXCEPTION_CAUSE_AI, str(exception))
    except Exception as e:
        print(e)
        exit(RETURN_ERROR)
    finally:
        lock.release()


def _make_gpt_request(snippet, ai_16k):
    prompt = f'''
        You are a developer for C helping me with my following question. I want to understand the typical process of code evolution by looking at how developers make changes over time for testing an incremental analysis of the static c analyzer Goblint.

        The following mutations are already generated by me. So please do not generate programs that can be generated by this mutations: {get_operator_descriptions_for_ai()}. Please do not consider these mutations as examples for how your code changes should look like. Just try to prevent doing things that could be done with these mutations.

        Below is a snippet from a C file which represents a part of the finished program. My question is how a previous version of this code could have looked like before some typical code changes have been done by developers. Please generate me such a previous version!

        The code you generate should be a self-contained snippet that could directly replace the provided excerpt in the initial, complete program. It should preserve the overall functionality of the program and must not cause any compilation errors when reintegrated into the larger code base. Please consider the dependencies and interactions with other parts of the program when generating the previous version of the code. Your generated code should be able to interact correctly with the rest of the program just like the initial excerpt does. You do not have to add import statements or function declarations or closing brackets when these are cut off in the snippet, but when they are in the snippet you need to add them to preserve the whole program.

        Use these keywords (\"{SEPARATOR_EXPLANATION_START}\", \"{SEPARATOR_EXPLANATION_END}\", \"{SEPARATOR_CODE_START}\", \"{SEPARATOR_CODE_END}\") similar to html tags to structure you answer. You answer should have the following structure for identifying the different parts of the response, as it will be interpreted by another program: {SEPARATOR_EXPLANATION_START} (Response: Explain what you have changed in one or two sentences) {SEPARATOR_EXPLANATION_END} {SEPARATOR_CODE_START} (Response: the previous version of the code) {SEPARATOR_CODE_END}

        Here the code snippet:
        ```c
            {snippet}
        ```
        '''

    if ai_16k:
        model = AI_MODEL_16K
    else:
        model = AI_MODEL

    response = openai.ChatCompletion.create(
        model=model,
        n=1,
        messages=[
            {"role": "user", "content": prompt},
        ]
    )

    response_message = response.choices[0].message['content']
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens

    return response_message, prompt_tokens, completion_tokens


# Adjust interesing lines when they are exceeding the max file size
def _reformat_interesting_lines(num_selected_lines, interesting_lines, max_line):
    for i in range(len(interesting_lines)):
        interesting_lines[i] = int(interesting_lines[i])
        # Adjust for line array starting with 0 but in input first line is 1
        interesting_lines[i] -= 1
        # When line + num_selected_lines is greater than max_line correct the line downwards
        if interesting_lines[i] + num_selected_lines > max_line:
            interesting_lines[i] = max_line - num_selected_lines
    return interesting_lines


# select random start line
def _select_lines(interesting_lines, num_selected_lines, max_line):
    if not interesting_lines:
        selected_line = random.randint(0, max_line - num_selected_lines)
    else:
        selected_line = random.choice(interesting_lines)
    return range(selected_line, selected_line + num_selected_lines)


# check if passed interesting lines are correctly formatted
def validate_interesting_lines(interesting_lines_string: str, program_path):
    if program_path is not None:
        with open(program_path, "r") as file:
            max_line = len(file.readlines())
    else:
        max_line = None

    try:
        interesting_lines = ast.literal_eval(interesting_lines_string)
    except SyntaxError:
        print(
            f"{COLOR_RED}The format \"{interesting_lines_string}\" is incorrect! Please use a format like this: \"[1, 42, 99]\"{COLOR_RESET}")
        return None
    except Exception as e:
        print(
            f"{COLOR_RED}An unexpected error occurred reading the input \"{interesting_lines_string}\":{COLOR_RESET} {e}")
        return None

    if max_line is not None:
        for line in interesting_lines:
            if line <= 0:
                print(f"{COLOR_RED}All lines in \"{interesting_lines_string}\" should be greater zero!{COLOR_RESET}")
                return None
            if line > max_line:
                print(
                    f"{COLOR_RED}All lines in \"{interesting_lines_string}\" should be below the maximum line {max_line}!{COLOR_RESET}")
                return None

    return interesting_lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mutations with AI.")
    parser.add_argument("program", help="Path to the C program")
    parser.add_argument("apikey", help="Path to the api key")
    parser.add_argument("ai_count", help="How many different programs should be generated with AI")
    parser.add_argument("num_selected_lines", help="How many lines to consider")
    parser.add_argument('-m16', '--model-16k', action='store_true', help='Run with the 16k model instead of the 4k')

    args = parser.parse_args()

    generate_ai_mutations(args.program, args.apikey, int(args.ai_count), int(args.num_selected_lines), '[]', args.model_16k, 0)
