# MCP Composer Tool Filtering Test Summary

## Background

The goal of this initial test was to evaluate different tool filtering approaches
for the MCP composer. Without tool filtering, the required context will be too large for Large Language Models
(LLMs) to interact effectively with MCP Composer. This specific MCP composer instance contained 270 tools, mainly from instana. The test involved five distinct tool filtering approaches:

1. **Brute force**: LLM receives all tool information and selects a
   subset. This will eventually fail once the tool count causes the prompt
   to exceed the token limit; though, it does work for 270 tools.
2. **Clipped descriptions**: LLM receives just tool names and the
   first 75 characters of their descriptions. Typically this first sentence or so
   will summarize the purpose of the tool.
3. **Vector search (no LLM)**: Simple vector search for picking tools.
4. **Hybrid (vector + LLM)**: Combines vector search with LLM decision-making
   on a smaller subset of 25 tools picked by the vector search.
5. **Two-step LLM approach**: Narrows down the tool set using clipped
   descriptions and then picks from this subset with full length
   descriptions.

## Evaluation Questions & Answers

The following questions were used to assess each filtering method, and
their respective answers are shown below. This is a small initial test,
but eventually the question bank and the number of tools on the MCP composer instance
will have to be longer for more comprehensive results:

### Questions:

1. Show top erroneous calls handled by 'Robot Shop - EP' application since
   yesterday.
2. Show performance overview of all hup calls in the past 2 hours group by
   call name.
3. What is the average response time of promo HTTP calls handled by
   Kubernetes cluster demo-us-cluster?
4. What is the average response time of readiness calls handled by service
   app of application zone in last 1 day?
5. Show count of erroneous HTTP calls by call.tag.Errorcode handled by
   AdService application.
6. Show top erroneous calls handled by AdService service since last 10
   minutes.
7. Show performance overview of outbound HTTP calls from kubernetes
   cluster kub8-names to AC-test application order by calls.
8. What are the slowest API endpoints in my environment and their
   contributing factors (CPU, memory, dependencies) - use local tool only?

### Answers (required tools) :

- `getCallGroup`
- `getCallGroup`
- `getCallGroup`
- `getCallGroup`
- `getCallGroup`
- `getCallGroup`
- `getCallGroup`
- `getCallGroup`, `getServicesMetrics`

## Evaluation Criteria

A method was considered correct for a given question if all methods from
the corresponding answer were within its filtered output (limited to 10
tools). Average time in seconds for each approach is also recorded. Note this
time measurement is more of a relative heuristic rather than an actual speed
measurement due to build costs for each instance (approach + question).

## Test Results

| Name                                                         | Accuracy | Avg_time (s) |
| ------------------------------------------------------------ | -------- | ------------ |
| gpt 4o clipped descriptions --> full descriptions on subset  | 1.0      | 5.927        |
| gpt-4o brute force                                           | 1.0      | 22.330       |
| llama 4 clipped descriptions (name + 75 chars)               | 0.875    | 3.247        |
| gpt-4o clipped descriptions (name + 75 chars)                | 0.875    | 3.306        |
| Vector store open ai text-embedding-3-large                  | 0.875    | 4.589        |
| llama 4 brute force                                          | 0.875    | 5.808        |
| embedding-3-large -> llama4                                  | 0.875    | 6.013        |
| embedding-3-large -> 4o                                      | 0.875    | 6.329        |
| llama 4 clipped descriptions --> full descriptions on subset | 0.75     | 5.771        |
| vector store chromadb inbuilt model                          | 0.375    | 4.433        |
| chromadb -> 4o                                               | 0.375    | 6.178        |
| chromadb -> llama4                                           | 0.375    | 6.181        |
| vector store openai text-embedding-3-small                   | 0.125    | 4.313        |
| embedding-3-small -> llama4                                  | 0.125    | 5.385        |
| embedding-3-small -> 4o                                      | 0.125    | 5.773        |

## Observations

- The two-step LLM approach (`gpt 4o clipped descriptions --> full 
descriptions on subset`) demonstrates high accuracy (1.0) with a moderate
  time (5.927s).
- `gpt-4o brute force` also performed well with perfect accuracy (1.0),
  but at a significantly higher cost (22.330s).
- Other methods showed varying degrees of success, with the vector store
  approaches and smaller LLM models (`llama 4`, `embedding-3-small`) showing
  lower performance.
- Additional testing with >1000 tools and an expanded question set is
  planned to further validate these results and draw more definitive
  conclusions.
