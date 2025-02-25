import argparse
import subprocess
import sys
import threading

from util import *
from meta import *


# Run the tests
# The test_dir must be in the format xxx-tmp where xxx is a number >= 100
def run_tests(test_dir, goblint_repo_dir, cfg):
    # Change the number of the test directory to 99 for in place testing
    match = re.match(r'(\d+)-(.*)', os.path.basename(test_dir))
    if match:
        number, text = match.groups()
        number = int(number)
        if number > 99:
            number = 99
        new_name = f'{number}-{text}'
    else:
        print(f"\n{COLOR_RED}[ERROR] The test directory had not the format number-text{COLOR_RESET}", file=sys.stderr)
        meta_crash_and_store(META_CRASH_MESSAGE_RUN_TEST_NAME)
        sys.exit(RETURN_ERROR)

    # Check the group name of the test_dir
    if new_name != "99-TMP":
        print(f"\n{COLOR_RED}[ERROR] The test directory name has to be \'99-TMP\'{COLOR_RESET}", file=sys.stderr)
        meta_crash_and_store(META_CRASH_MESSAGE_RUN_TEST_NAME)
        sys.exit(RETURN_ERROR)

    # Copy the test file to the incremental tester
    incremental_tests_dir_abs = os.path.abspath(os.path.join(goblint_repo_dir, "tests", "incremental", new_name))
    if os.path.exists(incremental_tests_dir_abs):
        shutil.rmtree(incremental_tests_dir_abs)
    shutil.copytree(test_dir, incremental_tests_dir_abs)

    # Start running the tester
    ruby_path_abs = os.path.abspath(os.path.join(goblint_repo_dir, "scripts", "update_suite.rb"))
    initial_dir = os.getcwd()
    os.chdir(goblint_repo_dir)
    command = f"{ruby_path_abs} group TMP -i"
    if cfg:
        command += " -c"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)

    # Handle the output in a thread (Needed to correctly print the carriage return used by the ruby script)
    output_lines = []
    thread = threading.Thread(target=handle_output, args=(process, output_lines))
    thread.start()

    # Wait for processes to finish
    thread.join()
    process.wait()
    output = '\n'.join(output_lines)

    # Cleanup
    shutil.rmtree(incremental_tests_dir_abs)
    os.chdir(initial_dir)

    if process.returncode != 0:
        meta_test_failed(output)

    return process.returncode


def handle_output(process, output_lines):
    line = ''
    while True:
        char = process.stdout.read(1).decode('utf-8', 'replace')
        if not char and process.poll() is not None:
            break
        line = _print_char_to_line(char, line, output_lines)


def _print_char_to_line(char, line, output_lines):
    if char == '\r' or char == '\n':
        sys.stdout.write('\r' + line)
        sys.stdout.flush()
        if char == '\n':
            print()
            output_lines.append(line)
        line = ''
    else:
        line += char
    return line


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the tests in the specified test directory with the ruby script from Goblint')
    parser.add_argument('test_dir', help='Path to the directory with the tests (WARNING Will be removed!)')
    parser.add_argument('goblint_repo_dir', help='Path to the Goblint repository')
    parser.add_argument('-c', '--cfg', action='store_true', help='Run with fine-grained cfg-based change detection')

    args = parser.parse_args()

    run_tests(args.test_dir, args.goblint_repo_dir, args.cfg)
