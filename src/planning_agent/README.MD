# Planning Agent README

## Overview
This repository contains a planning agent designed to assist users in 
organizing tasks and workflows through the MCP composer. The agent processes user queries and 
generates a structured plan. The workflow involving five key steps: initialization, 
planning, revision, validation, and execution.

## Getting Started
To run the planning agent, follow these simple instructions:

1. Make sure the relevant env variables in .env_example are in your existing .env file. If not, add them accordingly.
2. Run an MCPComposer server in a separate terminal. 
3. Run the agent replacing `<user query>` with your actual input:
   ```bash
   bash -c "uv run planning_agent/client.py <user query>"
   ```

## Agent Workflow
Once initiated, the agent performs the following steps to construct a 
tailored workflow based on your query:

1. **Tool & Basic State Initialization**: The agent sets up necessary 
tools and initializes basic states required for processing the user's 
input. This includes loading relevant tools and initializing some state data 
structures in the State class. This is a temporary state implementation without a backend. 

2. **Planning**: In this phase, the agent analyzes the user's query to 
determine the desired outcome or goal. It then devises an initial plan 
in JSON format. It maps out the sequence of reasoning logic and tool calls 
that could potentially achieve the stated objective.

3. **Revision**: The initial plan generated is reviewed for feasibility 
and coherence. Revisions are made, if necessary, by optimizing the 
sequence or incorporating alternative strategies based on user feedback. If 
the user is happy with the plan they can /run it. 

4. **Validation**: The refined plan undergoes validation to ensure it 
adheres to constraints specified in the various tool schemas. Eventually, 
this step will also check appropriate authorization. 

5. **Execution**: Finally, the agent executes the workflow and outputs the answer.


## Random Example 
- uv run planning_agent/client.py is instana a server and if it is give me its first three tools


## Future Considerations: 
- Better formatting of the executed output
- Session Management 
- Context-aware tool exposure 
- Alternative validation, especially for OpenAPI specs where schemas are less transparent
- Authorization checks as part of validation 
- Storing successful plans on a user/system level, so that workflows can be repeated 