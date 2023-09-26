import os
import sys
import yaml
import configparser
import openai
import requests
import tiktoken
import json
import argparse
import time
from nltk.tokenize import sent_tokenize

# Flush the print statements as early as possible.
old_print = print

def new_print(*args, **kwargs):
    kwargs["flush"] = True
    old_print(*args, **kwargs)

print = new_print

# Function to count tokens
def count_tokens(text, encoding):
    tokenized_text = encoding.encode(text)
    return len(tokenized_text)

def send_to_gpt(section_type, text, prompts, default_prompt, max_tokens, encoding, test_mode=False):
    # Initialize variables
    default_tokens = count_tokens(default_prompt, encoding)
    prompts_tokens = sum(count_tokens(prompt, encoding) for prompt in prompts.values())
    tokens_to_submit = 0  # Initialize to 0 for new calculation
    responses = []
    
    # Break the text into blocks based on remaining token space
    text_blocks = []
    current_text = ""

    # Create a string containing all other prompts
    all_prompts = "\n".join(prompts.values())

    total_text_blocks = 0

    # Breaking the text down into "chunks" to submit individually.
    # We don't want to exceed the maximum token limit.
    for line in sent_tokenize(text):
        line_tokens = count_tokens(line, encoding)
        if tokens_to_submit + line_tokens + default_tokens + prompts_tokens <= max_tokens:
            line_plus_newline = line + " " 
            current_text += line_plus_newline
            tokens_to_submit += count_tokens(line_plus_newline, encoding)
        else:
            text_blocks.append(current_text.strip())
            line_plus_newline = line + " " 
            current_text = line_plus_newline
            tokens_to_submit = default_tokens + prompts_tokens + count_tokens(line_plus_newline, encoding)

    text_blocks.append(current_text.strip())  # Add the last remaining text block

    # Perform the API call for each text block
    total_token_tracker = 0
    start_time = time.time()

    for text_block in text_blocks:

        current_prompt = f"{default_prompt}\n{all_prompts}\n{text_block}"
        tokens_to_submit = count_tokens(current_prompt, encoding)

        # Check if adding tokens_to_submit exceeds the rate limit
        if total_token_tracker + tokens_to_submit > 9000:
            elapsed_time = time.time() - start_time
            if elapsed_time < 60:
                print("Rate limit approaching. Pausing for 65 seconds.")
                time.sleep(65)
            # Reset counters
            total_token_tracker = 0
            start_time = time.time()

        print(f"Section Type: {section_type}")
        print(f"Section has been split into {len(text_blocks)} block(s)")
        print(f"Estimated token submission: {tokens_to_submit}")

        if test_mode:
            continue
        else:
            message = [{"role": "user", "content": current_prompt}]
            response = openai.ChatCompletion.create(model=MODEL, messages=message, max_tokens=max_tokens)
            total_tokens_used = response['usage']['total_tokens']
            total_prompt_tokens = response['usage']['prompt_tokens']
            total_completion_tokens = response['usage']['completion_tokens']

            total_token_tracker += total_tokens_used  # Update the total tokens used
            print(f'Total tokens used: {total_tokens_used}')
            print(f'Actual prompt tokens: {total_prompt_tokens}')
            print(f'Total completion tokens: {total_completion_tokens}')
            print(f'Total tokens used so far: {total_token_tracker}')

            response_to_save = response['choices'][0]['message']['content']
            responses.append(response_to_save)

    return responses


# Read config file
config = configparser.ConfigParser()
config.read('config.cfg')

# Get config values
MAX_TOKENS = int(config['General']['MAX_TOKENS'])
MODEL = config['OpenAI']['model']
PROMPT_FILE_PATH = config['Prompts']['file_path']

# Get runtime arguments
api_key = os.environ.get('OPENAI_API_KEY', '')

# Initialize OpenAI and Entrez
openai.api_key = api_key

# Initialize encoding for tokenization
encoding = tiktoken.get_encoding("cl100k_base")

# Argument parser setup
parser = argparse.ArgumentParser(description='Process PubMed Central Articles')
parser.add_argument('pmc_id', help='PubMed Central ID of the article')
parser.add_argument('-f', '--file', help='Use a JSON file instead of fetching data from URL')
parser.add_argument('prompt_list', nargs='+', help='List of prompts to use')
parser.add_argument('--test', action='store_true', help='Run in test mode to only calculate tokens and submissions')
args = parser.parse_args()

def fetch_pmc_article(pmc_id, encoding='unicode', fmt='json'):
    url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{pmc_id}/unicode"

    print(f"Fetching article from {url}...")

    response = requests.get(url)
    
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        print(f"HTTP Error: {response.status_code}")
        return None

# Read YAML for prompts
with open(PROMPT_FILE_PATH, 'r') as f:
    all_prompts = yaml.safe_load(f)

# Filter out the relevant prompts based on command line arguments
prompts_dict = {key: all_prompts[key] for key in args.prompt_list if key in all_prompts and key != 'default'}

# Check for the existence of the 'default' key
if 'default' not in all_prompts:
    print("Error: Missing 'default' prompt in YAML file.")
    sys.exit(1)

# Load the default prompt
default_prompt = all_prompts['default']

default_prompt_token_count = count_tokens(default_prompt, encoding)

if args.file:
    with open(args.file, 'r') as f:
        article_data = json.load(f)
else:
    # Fetch PubMed Central Article
    article_data = fetch_pmc_article(args.pmc_id)

if not article_data:
    print("Failed to fetch the article.")
    sys.exit(1)

# Initialize a dictionary to hold the article sections
article_sections = {}

# Create a whitelist of section titles you want to include
# whitelist = ['ABSTRACT', 'INTRO', 'RESULTS', 'DISCUSSION', 'FIG']
whitelist = ['RESULTS', 'DISCUSSION']

# Initialize a dictionary to collect text for each section type
section_text_dict = {}

# Populate the dictionary with text snippets, grouped by section type
for document in article_data['documents']:
    for passage in document['passages']:
        section_type = passage['infons'].get('section_type', 'UNKNOWN').upper()
        if section_type in whitelist:
            if section_type not in section_text_dict:
                section_text_dict[section_type] = []
            section_text_dict[section_type].append(passage['text'])

# Print types of sections found.
print("Found the following sections:")
for section_type in section_text_dict:
    print(section_type)
print('-----------')

# Calculate and print the token count and submission count for each section
for section_type, section_texts in section_text_dict.items():
    combined_text = section_type + '\n' + ' '.join(section_texts)

    if args.test:
        send_to_gpt(section_type, combined_text, prompts_dict, default_prompt, MAX_TOKENS, encoding, test_mode=True)
    else:
        # In regular mode, send the text to GPT-3
        responses = send_to_gpt(section_type, combined_text, prompts_dict, default_prompt, MAX_TOKENS, encoding)
        print(f"Responses for section {section_type}:")
        for response in responses:
            print(response)
