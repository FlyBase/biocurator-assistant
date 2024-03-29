import os
import yaml
import time
import re
from openai import OpenAI
import argparse
import requests
import configparser
import json
from pathlib import Path

# Function to read configurations from config.cfg
def read_config(file_path):
    config = configparser.ConfigParser(interpolation=None)
    config.read(file_path)
    return config

# Function to find an existing assistant by name on the OpenAI platform.
def find_assistant_by_name(client, name):
    response = client.beta.assistants.list()
    for assistant in response.data:
        if assistant.name == name:
            return assistant
    return None

# Function to create a new biocurator assistant on OpenAI with specified parameters.
def create_biocurator_assistant(client, model, name='Biocurator', description='Assistant for Biocuration', tools_path=None, instructions=''):
    # Load custom tools from the JSON file if provided
    tools = []
    if tools_path:
        with open(tools_path, 'r') as file:
            tools = json.load(file)

    # Add the default 'retrieval' tool to the tools list
    tools.append({"type": "retrieval"})

    assistant = client.beta.assistants.create(
        name=name,
        description=description,
        model=model,
        tools=tools,
        instructions=instructions
    )
    return assistant

def get_or_create_biocurator_assistant(client, config, functions_json_path):
    existing_biocurator = find_assistant_by_name(client, 'Biocurator')

    if existing_biocurator:
        assistant_id = existing_biocurator.id
        print(f"Found existing Biocurator assistant with ID: {assistant_id}", flush=True)
        return assistant_id
    else:
        biocurator = create_biocurator_assistant(client, config['DEFAULT']['model'], 'Biocurator', 'Assistant for Biocuration', tools_path=functions_json_path, instructions=config['DEFAULT']['assistant_instructions'])
        if biocurator and biocurator.id:
            assistant_id = biocurator.id
            print(f"Created new Biocurator assistant with ID: {assistant_id}", flush=True)
            return assistant_id
        else:
            raise Exception("Assistant creation failed, no ID returned.")

# Function to upload a file to OpenAI and attach it to the assistant for processing.
def upload_and_attach_file(client, file_path, assistant_id):

    # Uploading the file to OpenAI.
    uploaded_file = client.files.create(file=Path(file_path), purpose='assistants')
    file_id = uploaded_file.id

    # Attaching the uploaded file to the assistant.
    assistant_file = client.beta.assistants.files.create(assistant_id=assistant_id, file_id=file_id)
    assistant_file_id = assistant_file.id
    return file_id, assistant_file_id

def process_input_files(client, assistant_id, input_files, config):
    file_ids = []
    for index, input_file in enumerate(input_files, start=1):
        print(f"Processing file: {input_file} ({index}/{len(input_files)})", flush=True)
        file_id, assistant_file_id = upload_and_attach_file(client, input_file, assistant_id)
        file_ids.append(file_id)

        process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, config['DEFAULT']['prompts_yaml_file'], config['DEFAULT']['output_dir'], input_file, int(config['DEFAULT']['timeout_seconds']))

        # Cleaning up by removing the file ID from the assistant
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            file_ids=[],
        )
    return file_ids

def delete_file_from_openai(client, file_id):
    try:
        response = client.files.delete(file_id)
        return response
    except Exception as e:
        print(f"Error: {e}", flush=True)

def clean_json_response(data):
    if isinstance(data, dict):
        return {k: clean_json_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_response(element) for element in data]
    elif isinstance(data, str):
        # Remove patterns like &#8203;``【oaicite:0】``&#8203; and [9†evidence]
        cleaned_data = re.sub(r"\[\d+†evidence\]|【.*?†source】", "", data)
        return cleaned_data
    else:
        return data

def process_json_output(output):
    try:
        data = json.loads(output) if isinstance(output, str) else output
        cleaned_data = clean_json_response(data)
        # Ensure Unicode characters are preserved
        return json.dumps(cleaned_data, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        return output  # Return original output if it's not valid JSON


def run_thread_return_last_message(client, thread_id, assistant_id, timeout_seconds):
    # Initiating the processing run.
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
    run_id = run.id

    # Checking periodically if the run has completed.
    start_time = time.time()
    while True:
        current_time = time.time()
        if current_time - start_time > timeout_seconds:
            print(f"Timeout: The operation took longer than {timeout_seconds} seconds.")
            print("-----", flush=True)
            print(f"Diagnostic information:")
            print(f"Run Status: {run.status}")
            print(f"Run Cancelled At: {run.cancelled_at}")
            print(f"Run Completed At: {run.completed_at}")
            print(f"Run Failed At: {run.failed_at}")
            print(f"Run Last Error: {run.last_error}")
            print("Proceeding to the next prompt.", flush=True)
            print("-----", flush=True)
            break

        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id,
        )

        if run.status == "requires_action":  # Check if the run requires action
            # Parse structured response from the tool call
            structured_response = json.loads(
                run.required_action.submit_tool_outputs.tool_calls[0].function.arguments
            )
            return structured_response
        elif run.status in ['failed', 'cancelled', 'expired']:
            if run.status == 'failed' and run.last_error is not None:
                print(f"Run failed: {run.last_error}", flush=True)
                raise Exception("Run failed.")
            elif run.status == 'cancelled':
                print("Run was cancelled.", flush=True)
            elif run.status == 'expired':
                print("Run expired.", flush=True)
            print("Proceeding to the next prompt.", flush=True)
            break

        time.sleep(5)  # Wait for 5 seconds before retrying

    raise Exception("Run did not complete in the expected manner.")

# Function to process queries using the Biocurator assistant.
def process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, yaml_file, output_dir, pdf_file, timeout_seconds):

    # Creating a new thread for processing.
    thread = client.beta.threads.create()
    thread_id = thread.id

    # Loading prompts from the YAML file.
    prompts = yaml.safe_load(open(yaml_file, 'r'))
    for prompt, value in prompts.items():
        print('Processing prompt: ' + prompt, flush=True)
        # Sending each prompt to the assistant for processing.
        thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=value,
        file_ids=[file_id])

        # Running the thread and retrieving the last message.
        final_text_to_write = run_thread_return_last_message(client, thread_id, assistant_id, timeout_seconds)

        # Cleaning and saving the processed content to an output file.
        output_file = Path(output_dir) / (pdf_file.stem + '_' + prompt + '.txt')
        with open(output_file, 'w') as f:
            cleaned_text = process_json_output(final_text_to_write)
            f.write(cleaned_text)

def cleanup_resources(client, file_ids, assistant_id):
    # Delete all uploaded files
    for file_id in file_ids:
        try:
            delete_file_from_openai(client, file_id)
        except Exception as e:
            print(f"Failed to delete file with ID {file_id}: {e}", flush=True)

    # Delete the assistant if it was created
    if assistant_id:
        try:
            print(f"Deleting assistant: {assistant_id}", flush=True)
            client.beta.assistants.delete(assistant_id)
        except Exception as e:
            print(f"Failed to delete assistant with ID {assistant_id}: {e}", flush=True)

def main():   
    assistant_id = None
    file_ids = []

    try:
        # Read configurations from the config.cfg file
        config = read_config('config.cfg')

        # Parsing command-line argument for the API key
        parser = argparse.ArgumentParser(description='Process files with OpenAI GPT-4 and Biocurator Assistant')
        parser.add_argument('--api_key', help='OpenAI API key', required=True)
        args = parser.parse_args()

        # Initializing the OpenAI client with the API key from the command line
        client = OpenAI(api_key=args.api_key)

        # Checking for an existing Biocurator assistant
        existing_biocurator = find_assistant_by_name(client, 'Biocurator')
        functions_json_path = 'functions.json'

        # Handling the existing or new assistant creation
        assistant_id = get_or_create_biocurator_assistant(client, config, functions_json_path)

        # Get the list of files to process
        input_dir = Path(config['DEFAULT']['input_dir'])
        input_files = sorted([f for f in input_dir.glob('*.pdf') if f.name != '.gitignore'])

        # Start the processing timer
        start_time = time.time()

        # Process each file
        file_ids = process_input_files(client, assistant_id, input_files, config)

        # Calculate and print the total time elapsed
        end_time = time.time()
        total_time_elapsed = end_time - start_time
        print(f"Total time elapsed: {total_time_elapsed:.2f} seconds")

        # Calculate the average time per file
        if len(input_files) > 0:
            average_time_per_file = total_time_elapsed / len(input_files)
            print(f"Average time per input file: {average_time_per_file:.2f} seconds")
        else:
            print("No files were processed.")

    except Exception as e:
        print(f"An error occurred: {e}", flush=True)

    finally:
        cleanup_resources(client, file_ids, assistant_id)

if __name__ == '__main__':
    main()