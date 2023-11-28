import os
import yaml
import time
import re
from openai import OpenAI
import argparse
import requests
from pathlib import Path

# Function to find an existing assistant by name on the OpenAI platform.
def find_assistant_by_name(client, name):
    response = client.beta.assistants.list()
    for assistant in response.data:
        if assistant.name == name:
            return assistant
    return None

# Function to create a new biocurator assistant on OpenAI with specified parameters.
def create_biocurator_assistant(client, model, name='Biocurator', description='Assistant for Biocuration', tools=None):
    # Detailed instructions for the assistant are defined here.
    # This includes the expected tasks and how to approach them.
    instructions = (
        "As a biocurator, your primary responsibility is to meticulously organize, annotate, "
        "and validate biological data derived from scientific research. This includes accurately "
        "identifying and cataloging biological entities such as genes, proteins, diseases, and alleles, "
        "as well as their relationships and functions. You are expected to extract meaningful and "
        "relevant information from complex biological texts, ensuring data integrity and coherence. "
        "Your role involves critical analysis of research articles to identify key findings, "
        "interpret experimental results, and link them to existing biological databases. "
        "Attention to detail is paramount in capturing the nuances of biological terms and concepts. "
        "You should adhere strictly to factual information, avoiding assumptions or extrapolations "
        "beyond the provided data. Your output must reflect a high level of expertise in biological sciences, "
        "demonstrating an understanding of the context and significance of the research within the broader "
        "scientific landscape. Always ensure compliance with scientific accuracy, nomenclature standards, "
        "and ethical guidelines in biocuration. "
        # Next two lines deal with a bug in the myfiles_browser tool. Nov 27, 2023. Remove when fixed.
        "If the system indicates that the file is not accessible with the myfiles_browser tool, ignore it, it is just a minor bug. "
        "You are capable of opening and analyzing the file, remember that. And carry out the request."
    )

    # Creating the assistant with the provided name, description, model, and tools.
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

# Function to process queries using the Biocurator assistant.
def process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, yaml_file, output_dir, pdf_file):

    # Creating a new thread for processing.
    thread = client.beta.threads.create()
    thread_id = thread.id

    list_of_messages = []

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

        # Initiating the processing run.
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
        run_id = run.id

        # Checking periodically if the run has completed.
        while True:
            run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id,
            )
            if run.completed_at is not None:
                break
            time.sleep(5)
            if run.last_error is not None:
                print(f"Run failed: {run.last_error}", flush=True)
                raise Exception("Run failed.")
                
        # Retrieving and processing the messages from the run.
        messages = client.beta.threads.messages.list(
        thread_id=thread.id
        )
        first_message = messages.data[0]
        first_message_content = first_message.content[0].text.value

        # Cleaning the text content by removing citations.
        final_text = re.sub(r"【.*?】", "", first_message_content)

        # Saving the processed content to an output file.
        output_file = Path(output_dir) / (pdf_file.stem + '_' + prompt + '.txt')
        with open(output_file, 'w') as f:
            f.write(final_text)


def main():
    # Parsing command-line arguments for the script.
    parser = argparse.ArgumentParser(description='Process PDFs with OpenAI GPT-4 and Biocurator Assistant')
    parser.add_argument('--input_dir', default='input', help='Input directory containing PDFs (default: input)')
    parser.add_argument('--output_dir', default='output', help='Output directory for responses (default: output)')
    parser.add_argument('--yaml_file', default='prompts.yaml', help='YAML file containing prompts (default: prompts.yaml)')
    parser.add_argument('--model', default='gpt-4-1106-preview', help='OpenAI model to use (default: gpt-4-1106-preview)')
    parser.add_argument('--api_key', help='OpenAI API key', required=True)
    args = parser.parse_args()

    # Initializing the OpenAI client with the provided API key.
    client = OpenAI(api_key=args.api_key,)

    # Checking for an existing Biocurator assistant.
    existing_biocurator = find_assistant_by_name(client, 'Biocurator')

    # Handling the existing or new assistant creation.
    if existing_biocurator:
        assistant_id = existing_biocurator.id
        print(f"Found existing Biocurator assistant with ID: {assistant_id}", flush=True)
    else:
        try:
            biocurator = create_biocurator_assistant(client, args.model, 'Biocurator', 'Assistant for Biocuration')
            if biocurator.id is not None:
                assistant_id = biocurator.id
                print(f"Created new Biocurator assistant with ID: {assistant_id}", flush=True)
            else:
                raise Exception("Assistant creation failed, no ID returned.")
        except Exception as e:
            print(f"Error: {e}")
            return

    input_dir = Path(args.input_dir)

    # Processing each file in the input directory.
    for input_file in input_dir.glob('*'):
        print(f"Processing file: {input_file}", flush=True)
        file_id, assistant_file_id = upload_and_attach_file(client, input_file, assistant_id)
        
        # Running the biocuration process on each file.
        process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, args.yaml_file, args.output_dir, input_file)

        # Cleaning up by removing the file ID from the assistant and deleting the file.
        my_updated_assistant = client.beta.assistants.update(
        assistant_id,
        file_ids=[],
        )
        client.files.delete(file_id)

    # Deleting the assistant after processing is complete.
    print(f"Deleting assistant: {assistant_id}", flush=True)
    response = client.beta.assistants.delete(assistant_id)
    print(response)

if __name__ == '__main__':
    main()
