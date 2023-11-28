# Biocurator Assistant with GPT-4

## Overview
Biocurator Assistant is a Dockerized tool leveraging OpenAI's GPT-4 for biocuration tasks. It processes PDF documents, extracting and analyzing scientific data for biological research, and manages data flow using AI techniques.

## Requirements
- Docker
- OpenAI API key

## Configuration
The behavior of the Biocurator Assistant is configured using a prompts.yaml file. This file contains structured prompts that guide the extraction of specific information from the scientific publications. Each entry in the YAML file represents a different type of information to be extracted, such as genes, alleles, diseases, and physical interactions between proteins. Feel free to modify this file as appropriate for your organism or field of study.

## How to Run
### Build the Docker Image
```docker build -t biocurator-assistant .```

### Run the Docker Container
```docker run -v $(pwd)/input:/usr/src/app/input -v $(pwd)/output:/usr/src/app/output biocurator-assistant python assistant.py --api_key <openai-api-key>```

- `<openai-api-key>`: Replace this with your actual OpenAI API key.
- Place your PDF files in the `input` directory before running the container.
- Output text files will be created in the `output` directory. These output files will follow the naming convention of ```PDF-name_prompt-title.txt```. For example, with a PDF named `zns11881` the resulting output file for a `genes` prompt would be `zns11881_genes.txt`

## Important Note About Cost
Processing PDFs using OpenAI's "assistants" approach uses around **300k+ context tokens** for each moderately-sized scientific publication. The total costs (as of Nov 28, 2023) are around **$2 per publication** for ~4 prompts. Please keep this in mind when running the script. Converting PDF -> text beforehand may reduce this cost (currently being tested).