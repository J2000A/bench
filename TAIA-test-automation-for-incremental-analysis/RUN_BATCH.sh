#!/bin/bash

# Start time for duration
SECONDS=0

# Check if the script is run from the correct location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CURRENT_DIR=$(pwd)
if [ "$SCRIPT_DIR" != "$CURRENT_DIR" ]; then
  echo "Script is NOT run from its own directory! Please change the directory to the location of the script."
  exit 1
fi

# Check if realpath is available
if ! command -v realpath &> /dev/null; then
    echo "realpath command is not available. Please install it."
    exit 1
fi

color_grey="\033[90m"
color_red="\033[31m"
color_blue='\033[34m'
color_green='\033[32m'
color_yellow="\033[33m"
color_orange="\033[38;5;208m"
color_reset="\033[0m"

no_print=false
ignore_files=()

# Check for at least one argument
if [ $# -lt 1 ]; then
    printf "Usage: $0 <directory> [--no-print] [--statistics] [--ignore <file_path>]* [additional arguments...]\n"
    printf "<directory>: path to a directory with the .c files for the batch\n"
    printf "[--no-print]: Do not print the Test Automation for Incremental Analysis (TAIA) output\n"
    printf "[--ignore <file_path>]* : paths to files containing paths to be ignored, separated by newlines\n"
    printf "[additional arguments...]: Arguments passed to Goblint to skip interactive cli.\n"
    printf "    -> Recommended: --enable-clang --disable-precision --enable-running --disable-create-tests --enable-cfg --goblint-config {}\n"
    printf "       or in short: --default\n"
    exit 1
fi

# Store directory and shift to get other arguments
dir=$1
shift

# Check if directory exists
if [ ! -d "$dir" ]; then
    printf "Directory $dir does not exist.\n"
    exit 1
fi

# Parse options
goblint_args=()
while (( "$#" )); do
  case "$1" in
    --no-print)
      no_print=true
      shift
      ;;
    --statistics)
      statistics=true
      shift
      ;;
    --ignore)
      ignore_files+=("$2")
      shift 2
      ;;
    *)
      goblint_args+=("$1")
      shift
      ;;
  esac
done

# Check for --statistics option
if [ "$statistics" = true ]; then
    timestamp=$(date "+%Y-%m-%d-%H-%M-%S")
    statistics_temp_dir=./out/stats-${timestamp}-temp-collector
    statistics_path=./out/stats-${timestamp}.yaml
    mkdir -p $statistics_temp_dir
fi



# Get ignore patters from ignore files
ignore_patterns=()
for ignore_file in "${ignore_files[@]}"; do
    while IFS= read -r line; do
        line=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        # if line is non-empty and does not start with #
        if [[ -n "$line" ]] && [[ "$line" != \#* ]]; then
            ignore_patterns+=("$line")
        fi
    done < <(cat "$ignore_file"; printf '\n') # Add newline to end of file
done

# Find .c files in subdirectories of the specified directory
files=$(find "$dir" -type f -name "*.c" | sort)
files_length=$(find "$dir" -type f -name "*.c" | wc -l)

# Iterate over the found files
index=0
for file in $files
do
    ((index=index+1))

    # Check if the file should be ignored
    file_realpath=$(realpath "$file")
    for pattern in "${ignore_patterns[@]}"; do
        if [[ "$pattern" == *\/\* ]]; then
            pattern="${pattern%%\/\*}"
            if [[ "$file_realpath" == *"$pattern"* ]]; then
                printf "${color_grey}[BATCH][${index}/${files_length}] Ignoring file $file with ignore pattern ${pattern}/*${color_reset}\n"
                ignored_files+=("$file")
                continue 2
            fi
        elif [[ "$file_realpath" == *"$pattern" ]]; then
            printf "${color_grey}[BATCH][${index}/${files_length}] Ignoring file $file with ignore pattern ${pattern}${color_reset}\n"
            ignored_files+=("$file")
                continue 2
        fi
    done

    # Run the command with remaining arguments
    printf "${color_blue}[BATCH][${index}/${files_length}] Processing file ($file)${color_reset}"
    trap 'kill -- -$$' SIGINT # Allow user to use ctrl + c
    if [ "$no_print" = true ]; then
        timeout 600 ./RUN.sh -i "$file" ${goblint_args[@]} > /dev/null
        ret_code=$?
    else
        printf "\n"
        timeout 600 ./RUN.sh -i "$file" ${goblint_args[@]}
        ret_code=$?
    fi
    trap - SIGINT

    # Check for different return values
    case $ret_code in
        0)
            printf "$\r${color_green}[BATCH][${index}/${files_length}] Test succeeded (${file})  "
            success_files+=("$file")
            ;;
        100)
            printf "$\r${color_orange}[BATCH][${index}/${files_length}] Test failed (${file})      "
            failed_files+=("$file")
            ;;
        101)
            printf "$\r${color_reset}[BATCH][${index}/${files_length}] The provided file did not compile with gcc (${file})"
            gcc_error_input+=("$file")
            ;;
        102)
            printf "$\r${color_reset}[BATCH][${index}/${files_length}] The provided file did not compile with gcc after cil transformation (${file})"
            gcc_error_cil+=("$file")
            ;;
        124)
            printf "$\r${color_yellow}[BATCH][${index}/${files_length}] Execution timed out after 5 minutes (${file})"
            timeout_files+=("$file")
            printf "command: \"-\"\ninput: $file\nn: 0\ncrash: true\ncrash_message: \"Timeout\"" > ./temp/meta.yaml
            ;;
        *)
            printf "$?$\r${color_red}[BATCH][${index}/${files_length}] Exception during execution (${file})"
            exception_files+=("$file")
            ;;
    esac
    printf "${color_reset}\n"

    # Copy the meta file to the statistics collector directory
    if [ "$statistics" = true ]; then
        num_zeros=$(echo -n $files_length | wc -c)
        format_string="%0${num_zeros}d"
        cp ./temp/meta.yaml $statistics_temp_dir/input-$(printf "$format_string" $index).yaml
    fi
    printf "\r"
    
done

ignored_length=${#ignored_files[@]}
success_length=${#success_files[@]}
failed_length=${#failed_files[@]}
exception_length=${#exception_files[@]}
error_gcc_input_length=${#gcc_error_input[@]}
error_gcc_cil_length=${#gcc_error_cil[@]}
timeout_length=${#timeout_files[@]}
printf "\n\n${color_blue}[BATCH] Batch finished running $files_length input files${color_reset}\n\n"

# Print all ignored files
if [ ${#ignored_files[@]} -ne 0 ]; then
    printf "${color_yellow}The following $ignored_length files were ignored:\n"
    for file in "${ignored_files[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all success files
if [ ${#success_files[@]} -ne 0 ]; then
    printf "${color_green}The following $success_length files were run successfully with all tests passing:\n"
    for file in "${success_files[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all files with gcc error
if [ ${#gcc_error_input[@]} -ne 0 ]; then
    printf "${color_reset}The following $error_gcc_input_length files did not compile with gcc:\n"
    for file in "${gcc_error_input[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all files with gcc cil error
if [ ${#gcc_error_cil[@]} -ne 0 ]; then
    printf "${color_reset}The following $error_gcc_cil_length files did not compile with gcc after cil transformation:\n"
    for file in "${gcc_error_cil[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all files with timeout
if [ ${#timeout_files[@]} -ne 0 ]; then
    printf "${color_yellow}The following $timeout_length files timed out:\n"
    for file in "${timeout_files[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all files for which the test failed
if [ ${#failed_files[@]} -ne 0 ]; then
    printf "${color_orange}The following $failed_length files failed the tests:\n"
    for file in "${failed_files[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print all files for which an exception occurred during execution
if [ ${#exception_files[@]} -ne 0 ]; then
    printf "${color_red}The following $exception_length files experienced an exception during execution:\n"
    for file in "${exception_files[@]}"; do
        printf "$file\n"
    done
    printf "${color_reset}\n"
fi

# Print summary
printf "\n[BATCH] Summary:\n"
printf "Total number of input files: $files_length\n"

if [ "$ignored_length" -eq 0 ]; then color=${color_grey}; else color=${color_yellow}; fi
printf "${color}Number of ignored files: $ignored_length\n"

if [ "$success_length" -eq 0 ]; then color=${color_grey}; else color=${color_green}; fi
printf "${color}Number of successfully executed files: $success_length\n"

if [ "$error_gcc_input_length" -eq 0 ]; then color=${color_grey}; else color=${color_reset}; fi
printf "${color}Number of files that did not compile with gcc: $error_gcc_input_length\n"

if [ "$error_gcc_cil_length" -eq 0 ]; then color=${color_grey}; else color=${color_reset}; fi
printf "${color}Number of files that did not compile with gcc after cil transformation: $error_gcc_cil_length\n"

if [ "$timeout_length" -eq 0 ]; then color=${color_grey}; else color=${color_yellow}; fi
printf "${color}Number of timed out files: $timeout_length\n"

if [ "$failed_length" -eq 0 ]; then color=${color_grey}; else color=${color_orange}; fi
printf "${color}Number of files that failed the tests: $failed_length\n"

if [ "$exception_length" -eq 0 ]; then color=${color_grey}; else color=${color_red}; fi
printf "${color}Number of files that experienced an exception during execution: $exception_length\n"

printf $color_reset

# Stop time for duration
duration=$SECONDS

hours=$((duration / 3600))
minutes=$((duration / 60 % 60))
seconds=$((duration % 60))
printf "\nTotal execution time: ${color_yellow}%02d:%02d:%02d${color_reset} (HH:MM:SS) or %d seconds\n" $hours $minutes $seconds $duration

# Print statistics
if [ "$statistics" = true ]; then
    printf "${color_grey}Merging statistic...${color_reset}"
    python3 ./scripts/stats.py $statistics_path --merge $statistics_temp_dir --total-execution-time $duration
    printf "\r"
    python3 ./scripts/stats.py $statistics_path
fi
