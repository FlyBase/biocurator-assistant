# ChatGPT Curator

## Overview

ChatGPT Curator is a Python-based tool designed for biocuration tasks. It retrieves scientific articles from Pubmed Central based on a provided PMC ID, and then submits sections of the article to ChatGPT for various types of queries.

## Requirements

- Docker
- OpenAI API key

## Configuration

Configuration settings can be modified in `config.cfg`.

- `MAX_TOKENS`: The maximum number of tokens that can be sent to ChatGPT. Default is 4096.
- `model`: The ChatGPT engine to be used. Default is `gpt-4`.
- `file_path`: The path to the YAML file containing the prompts. Default is `prompts.yaml`.

## How to Run

### Build the Docker Image

```bash
docker build -t chatgpt_curator .
```
### Run the Docker Container
```bash
docker run -e OPENAI_API_KEY=your_openai_api_key chatgpt_curator <pmc_id> <-f test.json> <--test> <prompt_list>
```
- `your_openai_api_key`: Replace this with your actual OpenAI API key.
- `<pmc_id>`: The PMC ID of the article you wish to curate.
- `<-f test.json>`: OPTIONAL. Run a query using a local test.json file (example included in repo).
- `<--test>`: OPTIONAL. Process the data without submitting to ChatGPT. Useful for determining token usage and checking submissions.
- `<prompt_list>`: A space-separated list of prompt keys to use, e.g., genes alleles disease.

#### Example commands
- Run a gene query using the local test.json file (PMC still required but not used). This will submit data to ChatGPT.
  - `docker run -e OPENAI_API_KEY=sk-xxxx chatgpt_curator PMC7541083 -f test.json genes`

- Run a query by retrieving a paper from Pubmed Central and querying two prompts. This will submit data to ChatGPT.
  - `docker run -e OPENAI_API_KEY=sk-xxxx chatgpt_curator PMC10499800 genes allele`

- Run a test query by retrieving a paper from Pubmed Central and querying two prompts. This will NOT submit data to ChatGPT.
  - `docker run -e OPENAI_API_KEY=sk-xxxx chatgpt_curator PMC10499800 genes allele --test`

### How to Modify Prompts
Edit the prompts.yaml file to modify, add, or remove prompts.

```yaml
genes: "What genes are discussed in this article?"
alleles: "Are there any notable alleles?"
triage: "Summarize the key findings for triage."
```
Each key represents a prompt that will be used to query GPT. The key should be one word, and the value should be the actual prompt.
