import sys
import time
from typing import Tuple

import yaml

from util import GenerateType

META_FILENAME = 'meta.yaml'
META_PATH = 'meta_path'
META_INPUT = 'input'
META_FILESIZE = 'filesize_bytes'
META_N = 'n'
META_COMMAND = 'command'
META_TEST_FAILED = 'test_failed'
META_TEST_OUTPUT = 'test_output'
META_CRASH = 'crash'
META_CRASH_MESSAGE = 'crash_message'
META_EXCEPTION = 'exception'
META_EXCEPTION_CAUSE = 'exception_cause'
META_EXCEPTION_STD_OUT = 'exception_stdout'
META_EXCEPTION_STD_ERR = 'exception_stderr'
META_DIFF_EMTPY = 'diff_empty'
META_DIFF_ADDED = 'diff_added'
META_DIFF_REMOVED = 'diff_removed'
META_TYPE = 'type'
META_SUB_TYPE = 'subtype'
META_LINES = 'lines'
META_PROMPT_TOKENS = 'tokens_prompt'
META_COMPLETION_TOKENS = 'tokens_completion'
META_VARS = 'vars'
META_EVALS = 'evals'
META_NARROW_REUSES = 'narrow_reuses'
META_VARS_INCREMENTAL = 'vars_incremental'
META_EVALS_INCREMENTAL = 'evals_incremental'
META_NARROW_REUSES_INCREMENTAL = 'narrow_reuses_incremental'

META_EXCEPTION_CAUSE_MUTATION_GCC = 'mutation_gcc'
META_EXCEPTION_CAUSE_CREATE_CHECK_PROCESS = 'create_check_process'
META_EXCEPTION_CAUSE_CREATE_CHECK_GCC = 'create_check_gcc'
META_EXCEPTION_CAUSE_VERIFY_CHECK = 'verify_check'
META_EXCEPTION_CAUSE_AI = 'ai_request'
META_EXCEPTION_CAUSE_MUATION_NOT_APPLIED = 'mutation_not_applied'

META_CRASH_MESSAGE_INITIAL_EXCEPTION_GCC = 'initial_program_exception_gcc'
META_CRASH_MESSAGE_INITIAL_EXCEPTION_ADD_CHECK_PROCESS = 'initial_program_exception_add_check_process'
META_CRASH_MESSAGE_INITIAL_EXCEPTION_ADD_CHECK_GCC = 'initial_program_exception_add_check_gcc'
META_CRASH_MESSAGE_CLANG_LINE_GROUPS = 'exception_in_clang_line_groups'
META_CRASH_MESSAGE_CLANG_APPLY = 'exception_in_clang_apply'
META_CRASH_MESSAGE_CLANG_FUNCTION_NAME = 'exception_in_clang_function_name'
META_CRASH_MESSAGE_CLANG_WRAP = 'exception_in_clang_wrap'
META_CRASH_MESSAGE_RUN_TEST_NAME = 'run_test_naming_convention'
META_CRASH_MESSAGE_CREATE_TEST_NAME = 'create_test_naming_convention'
META_CRASH_MESSAGE_CREATE_TEST_EXISTS = 'create_test_directory_exists'
META_CRASH_MESSAGE_CREATE_TEST_MAX_EXCEEDED = 'create_test_max_dir_exceeded'
META_CRASH_MESSAGE_CREATE_TEST_PATCH = 'create_test_patch_error'

META_PERF_OVERALL = "perf_overall_ns"
META_PERF_PREP_PROGRAM = "perf_prepare_program_ns"
META_PERF_CLANG = "perf_clang_ns"
META_PERF_AI = "perf_ai_ns"
META_PERF_MUTATION_GCC = "perf_mutation_gcc_ns"
META_PERF_CHECKS_GENERATE = "perf_checks_generate_ns"
META_PERF_CHECKS_VERIFY = "perf_checks_verify_ns"
META_PERF_CHECKS_GCC = "perf_checks_gcc_ns"
META_PERF_GENERATE_TESTS = "perf_write_tests_ns"
META_PERF_RUN_TESTS = "perf_run_tests_ns"

_DATA = None


# Get index used for storing information about each muatation
def _meta_index(index):
    return f'p_{index}'


def write_meta_file():
    global _DATA
    if _DATA is None: return
    meta_path = _DATA.pop(META_PATH, None)
    if meta_path is None:
        raise Exception('The meta file was saved before or was not created!')
    with open(meta_path, 'w') as file:
        yaml.safe_dump(_DATA, file)


# Create file that will be stored in the global variable _DATA and will be at the end of execution written to the disk. 
def meta_create_file(meta_path, source_path):
    global _DATA
    if meta_path is None: return
    _DATA = {META_N: 0, META_PATH: meta_path, META_INPUT: source_path, META_COMMAND: f'python3 {" ".join(sys.argv)}',
             _meta_index(0): {META_TYPE: GenerateType.INPUT.value}}


def meta_add_filesize(file_bytes):
    global _DATA
    if _DATA is None: return
    _DATA[META_FILESIZE] = file_bytes


def meta_get_n() -> int:
    global _DATA
    if _DATA is None: return 0
    return _DATA[META_N]


def meta_set_n(n: int):
    global _DATA
    if _DATA is None: return
    _DATA[META_N] = n


def meta_create_index(index, main_type, sub_type, lines):
    global _DATA
    if _DATA is None: return
    _DATA[_meta_index(index)] = {
        META_TYPE: main_type,
        META_SUB_TYPE: sub_type,
        META_LINES: lines
    }


def meta_store_incremental_stats(variables, evals, narrow_reuses, index):
    global _DATA
    _DATA[_meta_index(index)].update({
        META_VARS: variables,
        META_EVALS: evals,
        META_NARROW_REUSES: narrow_reuses
    })


def meta_store_evals_incremental(variables, evals, narrow_reuses, index):
    global _DATA
    _DATA[_meta_index(index)].update({
        META_VARS_INCREMENTAL: variables,
        META_EVALS_INCREMENTAL: evals,
        META_NARROW_REUSES_INCREMENTAL: narrow_reuses
    })


def meta_exception(index, cause, cmd_result_or_string):
    global _DATA
    if _DATA is None: return
    if isinstance(cmd_result_or_string, str):
        stdout = cmd_result_or_string
        stderr = ''
    else:
        stdout = cmd_result_or_string.stdout
        stderr = cmd_result_or_string.stderr
    _DATA[_meta_index(index)].update({
        META_EXCEPTION: True,
        META_EXCEPTION_CAUSE: cause,
        META_EXCEPTION_STD_OUT: stdout,
        META_EXCEPTION_STD_ERR: stderr
    })


def meta_exception_exists(index):
    global _DATA
    if _DATA is None: return False
    return _DATA.get(_meta_index(index), {}).get(META_EXCEPTION, False)


def meta_get_type_and_subtype(index):
    global _DATA
    if _DATA is None: return
    main_type = _DATA.get(_meta_index(index), {}).get(META_TYPE, '')
    sub_type = _DATA.get(_meta_index(index), {}).get(META_SUB_TYPE, '')
    return main_type, sub_type


def meta_diff_empty(index):
    global _DATA
    if _DATA is None: return
    _DATA[_meta_index(index)][META_DIFF_EMTPY] = True


def meta_diff(added_count, removed_count, index):
    global _DATA
    if _DATA is None: return
    _DATA[_meta_index(index)][META_DIFF_ADDED] = added_count
    _DATA[_meta_index(index)][META_DIFF_REMOVED] = removed_count


def meta_crash_and_store(message):
    global _DATA
    if _DATA is None: return
    _DATA[META_CRASH] = True
    _DATA[META_CRASH_MESSAGE] = message
    write_meta_file()


def meta_test_failed(output):
    global _DATA
    if _DATA is None: return
    _DATA[META_TEST_FAILED] = True
    _DATA[META_TEST_OUTPUT] = output


def meta_start_performance(title: str) -> tuple[str, int]:
    current_ns = time.perf_counter_ns()
    return title, current_ns


def meta_stop_performance(start_performance):
    global _DATA
    if _DATA is None: return
    current_ns = time.perf_counter_ns()
    (title, start_ns) = start_performance
    duration_ns = current_ns - start_ns
    _DATA[title] = duration_ns + _DATA.get(title, 0)


def meta_add_ai_tokens(prompt_tokens, completion_tokens, index):
    global _DATA
    if _DATA is None: return
    _DATA[_meta_index(index)][META_PROMPT_TOKENS] = prompt_tokens
    _DATA[_meta_index(index)][META_COMPLETION_TOKENS] = completion_tokens
    return _DATA


# Collection of stats
def stats_get_performance(data):
    return [
        ('Overall', data.get(META_PERF_OVERALL, 0) // 1000000),
        ('Pre-processing', data.get(META_PERF_PREP_PROGRAM, 0) // 1000000),
        ('Clang', data.get(META_PERF_CLANG, 0) // 1000000),
        ('AI', data.get(META_PERF_AI, 0) // 1000000),
        ('Gcc Mutation', data.get(META_PERF_MUTATION_GCC, 0) // 1000000),
        ('Generate Checks', data.get(META_PERF_CHECKS_GENERATE, 0) // 1000000),
        ('Verify Checks', data.get(META_PERF_CHECKS_VERIFY, 0) // 1000000),
        ('Gcc Checks', data.get(META_PERF_CHECKS_GCC, 0) // 1000000),
        ('Generate Tests', data.get(META_PERF_GENERATE_TESTS, 0) // 1000000),
        ('Run Tests', data.get(META_PERF_RUN_TESTS, 0) // 1000000)
    ]


def stats_get_mutation_by_type_subtype(data):
    return _stats_get_by_type_subtype(data, (lambda index: 1))


def stats_get_empty_diff_by_type_subtype(data):
    return _stats_get_by_type_subtype(data, (
        lambda index: 1 if data.get(_meta_index(index), {}).get(META_DIFF_EMTPY, False) else 0))


def stats_get_exception_by_type_subtype(data):
    return _stats_get_by_type_subtype(data, (
        lambda index: 1 if data.get(_meta_index(index), {}).get(META_EXCEPTION, False) else 0))


def stats_get_failed_tests(data):
    return 1 if data.get(META_TEST_FAILED, False) else 0


def stats_get_evals_by_type(data):
    n = data[META_N]
    evals_by_type = []
    for index in range(1, n + 1):
        evals = data.get(_meta_index(index), {}).get(META_EVALS, -1)
        evals_inc = data.get(_meta_index(index), {}).get(META_EVALS_INCREMENTAL, -1)
        if evals >= 0:
            evals_by_type.append(('Evals (non incremental)', evals))
        if evals_inc >= 0:
            evals_by_type.append(('Evals (incremental)', evals_inc))
    return evals_by_type


def stats_get_vars_by_type(data):
    n = data[META_N]
    vars_by_type = []
    for index in range(1, n + 1):
        variables = data.get(_meta_index(index), {}).get(META_VARS, -1)
        vars_inc = data.get(_meta_index(index), {}).get(META_VARS_INCREMENTAL, -1)
        if variables >= 0:
            vars_by_type.append(('Vars (non incremental)', variables))
        if vars_inc >= 0:
            vars_by_type.append(('Vars (incremental)', vars_inc))
    return vars_by_type


def stats_get_crash(data):
    return 1 if data.get(META_CRASH, False) else 0


def stats_get_exceptions_by_cause(data):
    n = data[META_N]
    mutation_types = []
    for index in range(1, n + 1):
        if not data.get(_meta_index(index), {}).get(META_EXCEPTION, False):
            continue
        cause = data.get(_meta_index(index), {}).get(META_EXCEPTION_CAUSE, '')
        mutation_types.append((f'{cause}', 1))
    return mutation_types


def stats_get_crash_by_message(data):
    if not data.get(META_CRASH, False):
        return []
    return [(data.get(META_CRASH_MESSAGE, ''), 1)]


def _stats_get_by_type_subtype(data, lambda_function):
    n = data[META_N]
    mutation_types = []
    for index in range(1, n + 1):
        main_type = data.get(_meta_index(index), {}).get(META_TYPE, '')
        sub_type = data.get(_meta_index(index), {}).get(META_SUB_TYPE, '')
        if main_type == GenerateType.AI.value:  # if type is AI set subtype to 'openai' as the subtype varies
            sub_type = 'openai'
        mutation_types.append((f'{main_type}-{sub_type}', lambda_function(index)))
    return mutation_types


def stats_get_tokens(data):
    n = data[META_N]
    token_list = []
    for index in range(1, n + 1):
        tokens_prompt = data.get(_meta_index(index), {}).get(META_PROMPT_TOKENS, -1)
        tokens_completion = data.get(_meta_index(index), {}).get(META_COMPLETION_TOKENS, -1)
        if tokens_prompt > 0 or tokens_completion > 0:
            token_list.append(('Prompt Tokens', tokens_prompt))
            token_list.append(('Completion Tokens', tokens_completion))
            token_list.append(('Total Tokens', tokens_prompt + tokens_completion))
    return token_list


def stats_get_patch_changes(data):
    n = data[META_N]
    changes_list = []
    for index in range(1, n + 1):
        added = data.get(_meta_index(index), {}).get(META_DIFF_ADDED, -1)
        removed = data.get(_meta_index(index), {}).get(META_DIFF_REMOVED, -1)
        if added >= 0 and removed >= 0:
            changes_list.append(('Added lines', added))
            changes_list.append(('Removed lines', removed))
    return changes_list
