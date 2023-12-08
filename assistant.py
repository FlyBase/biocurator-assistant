import os
import yaml
import time
import re
from openai import OpenAI
import argparse
import requests
import configparser
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
def create_biocurator_assistant(client, model, name='Biocurator', description='Assistant for Biocuration', tools=None, instructions=''):
    assistant = client.beta.assistants.create(
        name=name,
        description=description,
        model=model,
        tools=tools if tools else [{"type": "retrieval"}],
        instructions=instructions
    )
    return assistant
    
# Function to upload a file to OpenAI and attach it to the assistant for processing.
def upload_and_attach_file(client, file_path, assistant_id):

    # Uploading the file to OpenAI.
    uploaded_file = client.files.create(file=Path(file_path), purpose='assistants')
    file_id = uploaded_file.id

    # Attaching the uploaded file to the assistant.
    assistant_file = client.beta.assistants.files.create(assistant_id=assistant_id, file_id=file_id)
    assistant_file_id = assistant_file.id
    return file_id, assistant_file_id

# Function to delete a file from OpenAI's platform.
def delete_file_from_openai(file_id):
    try:
        response = openai.File.delete(file_id)
        print(response)
        return response
    except openai.error.OpenAIError as e:
        print(f"Error: {e}")

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

            if run.status == 'completed':
                break
            if run.status == 'failed':
                if run.last_error is not None:
                    print(f"Run failed: {run.last_error}", flush=True)
                raise Exception("Run failed.")
            if run.status == 'cancelled':
                print("Run was cancelled.", flush=True)
                print("This may be due to a timeout or an error.", flush=True)
                print("Proceeding to the next prompt.", flush=True)
                break
            if run.status == 'expired':
                print("Run expired.", flush=True)
                print("This may be due to a timeout or an error.", flush=True)
                print("Proceeding to the next prompt.", flush=True)
                break
            time.sleep(5)

        # Retrieving and processing the messages from the run.
        messages = client.beta.threads.messages.list(
        thread_id=thread_id
        )
        
        first_message = messages.data[0]
        first_message_content = first_message.content[0].text.value

        # Cleaning the text content by removing citations.
        final_text = re.sub(r"【.*?】", "", first_message_content)

        return final_text

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
        final_text = run_thread_return_last_message(client, thread_id, assistant_id, timeout_seconds)

        # Create the error correction prompt.
        intro_message = '''Below is the prompt you were given 
        for the last message and the output you returned. 
        DO NOT REFERENCE OR USE THE UPLOADED FILE.
        Please only check to see if your "reasoning" field matches the "triage_result" field in the JSON you created. 
        Please use the logic declared at the end of your last prompt below to verify this request.
        Typically, it does match, but sometimes there's a mistake. 
        If it looks OK, please output the same JSON as before and add a two fields "adjustments" and "adjustments_true_false".
        In "adjustments", please indicate your reason for not changing the "triage_result" field. In the "adjustments_true_false" field, please write false.
        If it looks wrong, please change the "triage_result" field ONLY, output the fixed JSON with two new fields "adjustments" and "adjustments_true_false".
        In "adjustments", please indicate your reason for changing the data. In the "adjustments_true_false" field, please write true.
        DO NOT output any additional text outside of the JSON. DO NOT edit the existing "reasoning" field.
        Thank you.'''

        # Combine the intro_message with the prompt and the final_text separated by a newline.
        error_correction_prompt = intro_message + "\nOriginal prompt:\n" + value + "\nPreviously generated response:\n" + final_text

        # Add this to the thread as a message.
        thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=error_correction_prompt)

        # Remove the file from the assistant before running the thread again.
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            file_ids=[],
        )

        # Run the thread again and retrieve the last message.
        final_text_to_write = run_thread_return_last_message(client, thread_id, assistant_id, timeout_seconds)

        # Saving the processed content to an output file.
        output_file = Path(output_dir) / (pdf_file.stem + '_' + prompt + '.txt')
        with open(output_file, 'w') as f:
            f.write(final_text_to_write)

def main():
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

    # Handling the existing or new assistant creation
    if existing_biocurator:
        assistant_id = existing_biocurator.id
        print(f"Found existing Biocurator assistant with ID: {assistant_id}", flush=True)
    else:
        try:
            biocurator = create_biocurator_assistant(client, config['DEFAULT']['model'], 'Biocurator', 'Assistant for Biocuration', instructions=config['DEFAULT']['assistant_instructions'])
            if biocurator.id is not None:
                assistant_id = biocurator.id
                print(f"Created new Biocurator assistant with ID: {assistant_id}", flush=True)
            else:
                raise Exception("Assistant creation failed, no ID returned.")
        except Exception as e:
            print(f"Error: {e}")
            return

    input_dir = Path(config['DEFAULT']['input_dir'])

    # Processing each file in the input directory
    for input_file in input_dir.glob('*'):
        if input_file.name == '.gitignore':
            continue  # Skip processing .gitignore file
        print(f"Processing file: {input_file}", flush=True)
        file_id, assistant_file_id = upload_and_attach_file(client, input_file, assistant_id)

        # Running the biocuration process on each file
        process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, config['DEFAULT']['prompts_yaml_file'], config['DEFAULT']['output_dir'], input_file, int(config['DEFAULT']['timeout_seconds']))

        # Cleaning up by removing the file ID from the assistant and deleting the file
        my_updated_assistant = client.beta.assistants.update(
            assistant_id,
            file_ids=[],
        )
        client.files.delete(file_id)

    # Deleting the assistant after processing is complete
    print(f"Deleting assistant: {assistant_id}", flush=True)
    response = client.beta.assistants.delete(assistant_id)
    # Uncomment for debugging purposes
    # print(response)

if __name__ == '__main__':
    main()