# Biocurator Assistant with GPT-4
## Overview
Biocurator Assistant is a Dockerized tool leveraging OpenAI's GPT-4 model for biocuration tasks. It processes PDF or text documents, extracting and analyzing scientific data for biological research. The tool creates a custom Assistant using OpenAI's Assistants API, which is tailored to manage data flow and perform specific curation tasks using AI techniques.

## Requirements
- Docker
- OpenAI API key

## Configuration
Configuration of the Biocurator Assistant is managed through a `config.cfg` file. This file allows you to set key parameters such as input and output directories, the YAML file containing prompts, and the model to be used. The `assistant_instructions` parameter in the `config.cfg` file contains detailed instructions for the Assistant, guiding its data processing and analysis behavior. Modify the `config.cfg` as needed to tailor the tool to your specific requirements.

### Key Settings in `config.cfg`
- `input_dir`: Directory for input files (PDFs or text documents).
- `output_dir`: Directory where output files will be saved.
- `prompts_yaml_file`: YAML file containing structured prompts for data extraction.
- `timeout_seconds`: The time in seconds to wait before timing out with an OpenAI API Assistant run.
- `model`: OpenAI model to be used by the Assistant.
- `assistant_instructions`: Detailed instructions for the Assistant, defining its operational scope and approach.

## How to Run
### Build the Docker Image
```docker build -t biocurator-assistant .```

### Run the Docker Container
```docker run -v $(pwd)/input:/usr/src/app/input -v $(pwd)/output:/usr/src/app/output biocurator-assistant python assistant.py --api_key <openai-api-key>```

- `<openai-api-key>`: Replace this with your actual OpenAI API key.
- Place your PDF or text files in the `input` directory before running the container.
- Output text files will be created in the `output` directory. These output files will follow the naming convention of ```PDF-name_prompt-title.txt```. For example, with a PDF named `zns11881` the resulting output file for a `genes` prompt would be `zns11881_genes.txt`

## Important Note About Cost
Processing PDFs using OpenAI's "assistants" approach uses around **300k+ context tokens** for each moderately-sized scientific publication. The total costs (as of Nov 28, 2023) are around **$2 per publication** for ~4 prompts. Please keep this in mind when running the script. Converting PDF -> text beforehand may reduce this cost (currently being tested).