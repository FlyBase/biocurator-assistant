import os
import yaml
import time
import re
from openai import OpenAI
import argparse
import requests
from pathlib import Path

# Function to find an existing assistant by name
def find_assistant_by_name(client, name):
    response = client.beta.assistants.list()
    for assistant in response.data:
        if assistant.name == name:
            return assistant
    return None

def create_biocurator_assistant(client, model, name='Biocurator', description='Assistant for Biocuration', tools=None):
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

    assistant = client.beta.assistants.create(
        name=name,
        description=description,
        model=model,
        tools=tools if tools else [{"type": "retrieval"}],
        instructions=instructions
    )
    return assistant

# Function to upload a file to OpenAI and attach it to the assistant
def upload_and_attach_file(client, file_path, assistant_id):

    # Upload file
    uploaded_file = client.files.create(file=Path(file_path), purpose='assistants')
    file_id = uploaded_file.id

    # Attach file to assistant
    assistant_file = client.beta.assistants.files.create(assistant_id=assistant_id, file_id=file_id)
    assistant_file_id = assistant_file.id
    return file_id, assistant_file_id

def delete_file_from_openai(file_id):
    try:
        response = openai.File.delete(file_id)
        print(response)
        return response
    except openai.error.OpenAIError as e:
        print(f"Error: {e}")

def process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, yaml_file, output_dir, pdf_file):

    # Create the thread.
    thread = client.beta.threads.create()
    thread_id = thread.id

    list_of_messages = []

    # Load the yaml file and create the messages.
    prompts = yaml.safe_load(open(yaml_file, 'r'))
    for prompt, value in prompts.items():
        print('Processing prompt: ' + prompt, flush=True)
        thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=value,
        file_ids=[file_id])

        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
        run_id = run.id

        # Every 5 seconds, check if the run has completed.
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
                
        # Retrieve the messages from the run.
        messages = client.beta.threads.messages.list(
        thread_id=thread.id
        )

        # Extract the message content
        first_message = messages.data[0]

        # Assuming the first content of the message is of type 'text'
        first_message_content = first_message.content[0].text.value

        # Remove the citations for now, we can revisit this later.
        final_text = re.sub(r"【.*?】", "", first_message_content)

        # Write the response to the output file
        output_file = Path(output_dir) / (pdf_file.stem + '_' + prompt + '.txt')
        with open(output_file, 'w') as f:
            f.write(final_text)


def main():
    parser = argparse.ArgumentParser(description='Process PDFs with OpenAI GPT-4 and Biocurator Assistant')
    parser.add_argument('--input_dir', default='input', help='Input directory containing PDFs (default: input)')
    parser.add_argument('--output_dir', default='output', help='Output directory for responses (default: output)')
    parser.add_argument('--yaml_file', default='prompts.yaml', help='YAML file containing prompts (default: prompts.yaml)')
    parser.add_argument('--model', default='gpt-4-1106-preview', help='OpenAI model to use (default: gpt-4-1106-preview)')
    parser.add_argument('--api_key', help='OpenAI API key', required=True)
    args = parser.parse_args()

    client = OpenAI(api_key=args.api_key,)

    # Check if the Biocurator assistant already exists
    existing_biocurator = find_assistant_by_name(client, 'Biocurator')

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

    for pdf_file in input_dir.glob('*.pdf'):
        print(f"Processing file: {pdf_file}", flush=True)
        file_id, assistant_file_id = upload_and_attach_file(client, pdf_file, assistant_id)
        
        # Process queries using threads
        process_queries_with_biocurator(client, assistant_id, file_id, assistant_file_id, args.yaml_file, args.output_dir, pdf_file)

        # Remove the file_id from the assistant.
        my_updated_assistant = client.beta.assistants.update(
        assistant_id,
        file_ids=[],
        )

        # Delete the file.
        client.files.delete(file_id)

    # Delete the assistant.
    # Removing it seems to result in better results for subsequent runs? Less errors in file processing.
    print(f"Deleting assistant: {assistant_id}", flush=True)
    response = client.beta.assistants.delete(assistant_id)
    print(response)

if __name__ == '__main__':
    main()
