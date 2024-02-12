# Biocurator Assistant with GPT-4
## Overview
Biocurator Assistant is a Dockerized tool leveraging OpenAI's GPT-4 model for biocuration tasks. It processes PDF or text documents, extracting and analyzing scientific data for biological research. The tool creates a custom Assistant using OpenAI's Assistants API, which is tailored to manage data flow and perform specific curation tasks using AI techniques.

## Requirements
- Docker
- OpenAI API key

## Configuration
The Biocurator Assistant uses three main configuration files to control its behavior:

- `config.cfg`: This file manages essential settings:

    - `input_dir`: Directory containing your input PDFs or text files.
    - `output_dir`: Directory where the output files will be saved.
    - `prompts_yaml_file`: The YAML file containing prompts for data extraction.
    - `timeout_seconds`: Timeout duration for the OpenAI Assistant API.
    - `model`: The OpenAI model to be used (_e.g._, gpt-4-0125-preview).
    - `assistant_instructions`: Instructions for the Assistant's biocuration tasks.

- `functions.json`: This JSON file defines how the GPT-4 LLM should structure its output data. Create custom functions to match your extraction needs.

- `prompts.yaml`: This YAML file contains specific prompts that tell the LLM how to extract data from scientific publications.

**Please see the `config_examples` directory for samples of these configuration files.**

## Program Functionality
When the Biocurator Assistant is run, it follows these steps:

1.  **Configuration Loading**: Reads the `config.cfg` file to set up operational parameters.
2. **Assistant Initialization**: Checks for an existing assistant or creates a new one using settings from `config.cfg` and tools defined in `functions.json`.
3.  **File Processing**: Iterates over input files (PDFs or text documents) in the specified input directory. Each file is uploaded and attached to the assistant for processing.
4. **Data Extraction**: For each input file, the script uses prompts from `prompts.yaml` to guide the assistant in extracting relevant information.
5. **Response Processing**: The assistant's responses are processed and cleaned, removing any extraneous formatting or references.
6. **Output Generation**: Extracted data is saved in the output directory, with filenames following the format `<PDF-name>_<prompt-title>.txt`. For example, with a PDF named `zns11881.pdf`, the resulting output file for a `genes` prompt would be `zns11881_genes.txt`
7. **Resource Cleanup**: Upon completion, uploaded files are deleted from OpenAI, and the assistant is removed if it was created during the run.

**IMPORTANT**: The script attempts to remove files it has uploaded when the script finishes. Please be sure to login to the OpenAI API console manually to ensure the files are removed if the program stops working at any point. OpenAI charges a **daily storage fee** for your files and you may accidentally deplete your API balance.

## How to Run
### Build the Docker Image
```docker build -t biocurator-assistant .```

### Run the Docker Container
```docker run -v $(pwd)/input:/usr/src/app/input -v $(pwd)/output:/usr/src/app/output biocurator-assistant python assistant.py --api_key <openai-api-key>```

- `<openai-api-key>`: Replace this with your actual OpenAI API key.
- Place your PDF or text files in the `input` directory before running the container.

## Important Note About Cost
Processing PDFs using OpenAI's "assistants" approach uses around **300k+ context tokens** for each moderately-sized scientific publication. The total costs (as of Feb 12, 2024) are around **$1.30 per publication** for ~4 prompts. Please keep this in mind when running the script.