# Complete Guide: Using Model Mesh with Claude Desktop

This comprehensive guide covers everything you need to set up and use the Model Mesh Tool with Claude Desktop, including setup instructions, use cases, test prompts, and examples.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup Instructions](#setup-instructions)
3. [Quick Reference](#quick-reference)
4. [Use Cases](#use-cases)
5. [Test Prompts](#test-prompts)
6. [Example Prompts](#example-prompts)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

---

## Prerequisites

1. **Install Python dependencies:**
   ```bash
   pip install mcp-composer litellm
   # Optional: For Ollama provider
   pip install ollama
   ```

2. **Install and run Ollama:**
   ```bash
   # Install Ollama (if not already installed)
   # Visit: https://ollama.ai/
   
   # Start Ollama server
   ollama serve
   
   # Pull required models
   ollama pull ibm/granite3.3-guardian:8b
   ollama pull ibm/granite3.3-vision:2b
   ```

3. **Claude Desktop installed:**
   - Download from: https://claude.ai/download
   - At least Claude Desktop Pro plan required

---

## Setup Instructions

### Step 1: Create the Composer Script

Create a Python script that sets up the Model Mesh Composer. Save this as `model_mesh_claude.py`:

```python
#!/usr/bin/env python3
"""
Model Mesh Composer for Claude Desktop

This script sets up a Model Mesh Tool with Guardian and Vision models
for use with Claude Desktop via MCP.
"""

import asyncio
import os
from pathlib import Path

from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Model Mesh Composer for Claude Desktop.
    """
    # Create composer
    composer = MCPComposer("model-mesh-composer")
    
    # Disable default composer tools (optional)
    composer.disable_composer_tool()
    
    # Get the path to the example prompt config
    script_dir = Path(__file__).parent
    prompt_config_path = script_dir / "model_mesh_prompts.json"
    
    # Configure the Model Mesh Tool
    # Note: If some models are not available, the tool will:
    # - Show warnings during initialization
    # - Continue to work with available models
    # - Return graceful error messages when unavailable models are called
    model_mesh_tool = ModelMeshTool({
        "name": "model_mesh",
        "prompt_config_path": str(prompt_config_path),
        "model_config": {
            # Guardian model with Ollama provider (for think=True support)
            "guardian": {
                "model": "ibm/granite3.3-guardian:8b",
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "options": {
                    "think": True,
                    "temperature": 0
                }
            },
            # Vision model with Ollama provider
            "vision": {
                "model": "ibm/granite3.2-vision",
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            }
        },
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_provider": "litellm"
    })
    
    # Add the tool to the composer
    composer.add_tool(model_mesh_tool)
    
    # Setup member servers (if any)
    await composer.setup_member_servers()
    
    # Run in stdio mode for Claude Desktop
    await composer.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
```

Make the script executable:
```bash
chmod +x model_mesh_claude.py
```

### Step 2: Find Claude Desktop Config File

The Claude Desktop config file location depends on your OS:

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### Step 3: Configure Claude Desktop

1. **Open Claude Desktop**
2. **Go to:** `Claude → Settings → Developer`
3. **Click:** `Edit Config`
4. **Add the Model Mesh Composer** to the `mcpServers` section:

```json
{
  "mcpServers": {
    "model-mesh": {
      "command": "python3",
      "args": [
        "/absolute/path/to/model_mesh_claude.py"
      ],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434"
      }
    }
  }
}
```

**Example for macOS:**
```json
{
  "mcpServers": {
    "model-mesh": {
      "command": "python3",
      "args": [
        "/Users/yourusername/mcp-composer/example/model_mesh_claude.py"
      ],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434"
      }
    }
  }
}
```

### Step 4: Restart Claude Desktop

1. **Quit Claude Desktop completely**
2. **Restart Claude Desktop**
3. The Model Mesh Tool should now be available

---

## Quick Reference

### Natural Language Approach

✅ **Good prompts** - Task-focused, natural language:
- "Check if this content is safe"
- "Analyze this image description"
- "Summarize this text"

❌ **Avoid** - Implementation details:
- "Use the model_mesh tool with task='guardian'"
- "Call the ibm/granite3.3-guardian:8b model"
- "Use prompt_key='guardian_content_safety'"

### Common Use Cases

**Check if content is safe:**
```
Check if this is safe: "{content}"
```

**Moderate user comment:**
```
Moderate this comment: "{comment}"
```

**Analyze image:**
```
Analyze this image: "{description}"
```

**Summarize text:**
```
Summarize this: "{text}"
```

**Answer question:**
```
Answer this based on the context: Context: "{context}" Question: "{question}"
```

### Available Prompt Templates

Based on `model_mesh_prompts.json`, you have access to:

**Guardian Prompts:**
- `guardian_content_safety` - General safety assessment
- `guardian_toxicity_check` - Toxicity detection
- `guardian_policy_compliance` - Policy compliance checking
- `guardian_risk_assessment` - Risk assessment with scoring
- `guardian_content_moderation` - Content moderation decisions

**Vision Prompts:**
- `vision_analysis` - Image analysis
- `vision_object_detection` - Object detection

**Speech Prompts:**
- `speech_transcription` - Audio transcription
- `speech_sentiment` - Sentiment analysis

**Text Prompts:**
- `text_summarization` - Text summarization
- `text_qa` - Question answering

---

## Use Cases

### 1. Content Safety & Moderation

#### Basic Safety Check
**User Prompt:**
```
Can you check if this content is safe to publish? "Hello, this is a test message for our blog"
```

**Expected Behavior:**
- Claude should use the model_mesh tool
- Task: "guardian"
- Should analyze content safety and provide risk assessment

**Negative Example (Harmful Content):**
**User Prompt:**
```
Can you check if this content is safe to publish? "This is terrible and you're an idiot for posting this"
```

**Expected Behavior:**
- Claude should use guardian task
- Should detect harmful/toxic content
- Should provide risk assessment indicating unsafe content

#### Toxicity Detection
**User Prompt:**
```
I received this comment on my website. Is it toxic or harmful? "I strongly disagree with your opinion on this topic"
```

**Expected Behavior:**
- Claude uses guardian task
- Detects toxicity level
- Provides actionable feedback

**Negative Example (Toxic Content):**
**User Prompt:**
```
I received this comment on my website. Is it toxic or harmful? "You're a complete moron and your ideas are stupid"
```

**Expected Behavior:**
- Claude uses guardian task
- Should detect high toxicity level
- Should provide clear warning about harmful content

#### Policy Compliance
**User Prompt:**
```
Our company policy says: "No profanity, no personal attacks, be respectful." 
Does this user comment comply? "Thank you for your helpful feedback on the project"
```

**Expected Behavior:**
- Claude checks policy compliance
- Compares content against policies
- Identifies any violations

**Negative Example (Policy Violation):**
**User Prompt:**
```
Our company policy says: "No profanity, no personal attacks, be respectful." 
Does this user comment comply? "Your article is wrong and you don't know what you're talking about"
```

**Expected Behavior:**
- Claude uses guardian task
- Should identify policy violations (personal attack, disrespectful)
- Should provide clear violation report

#### Risk Assessment
**User Prompt:**
```
I'm planning to post this on social media. What's the risk level? 
"Excited to share our new product launch next week!"
```

**Expected Behavior:**
- Claude performs risk assessment
- Provides risk score and categories
- Suggests mitigation if needed

**Negative Example (High Risk Content):**
**User Prompt:**
```
I'm planning to post this on social media. What's the risk level? 
"I'm going to expose all the company secrets tomorrow"
```

**Expected Behavior:**
- Claude uses guardian task
- Should identify high risk level
- Should warn about potential consequences

#### Content Moderation Decision
**User Prompt:**
```
Should I allow this user comment on my blog? "This article was very informative, thanks!"
```

**Expected Behavior:**
- Claude makes moderation decision
- Provides reasoning
- Suggests action (allow/flag/block)

**Negative Example (Problematic Content):**
**User Prompt:**
```
Should I allow this user comment on my blog? "This is garbage and the author clearly has no idea what they're doing"
```

**Expected Behavior:**
- Claude uses guardian task
- Should recommend blocking or flagging
- Should identify harmful/disrespectful content

### 2. Image & Vision Analysis

#### Image Description Analysis
**User Prompt:**
```
Can you analyze this image for me? It shows a sunset over mountains with a lake in the foreground
```

**Expected Behavior:**
- Claude uses vision task
- Analyzes image description
- Provides detailed analysis

**Negative Example (Inappropriate Image Content):**
**User Prompt:**
```
Can you analyze this image for me? It shows violent content with weapons and disturbing scenes
```

**Expected Behavior:**
- Claude uses vision task
- Should identify inappropriate content
- May flag content for review

#### Object Detection
**User Prompt:**
```
What objects can you identify in this scene? There's a kitchen with a table, chairs, refrigerator, and stove
```

**Expected Behavior:**
- Claude detects objects
- Lists all identified items
- May provide spatial information

**Negative Example (Missing or Unclear Objects):**
**User Prompt:**
```
What objects can you identify in this scene? The image is very blurry and dark, making it hard to see anything clearly
```

**Expected Behavior:**
- Claude uses vision task
- Should note image quality issues
- May indicate limited object detection due to poor image quality

### 3. Text Processing

#### Text Summarization
**User Prompt:**
```
Can you summarize this article for me? "The quick brown fox jumps over the lazy dog. This is a classic pangram used for typing practice. It contains every letter of the alphabet at least once. Pangrams are useful for testing keyboards and fonts."
```

**Expected Behavior:**
- Claude uses text task
- Creates concise summary
- Preserves key information

**Negative Example (Very Long/Complex Content):**
**User Prompt:**
```
Can you summarize this article for me? [Very long article with 10,000+ words covering multiple topics, technical jargon, and complex concepts]
```

**Expected Behavior:**
- Claude uses text task
- May hit token limits
- Should provide summary within constraints

#### Question Answering
**User Prompt:**
```
Based on this context: "Python is a programming language known for its simplicity and readability. It's widely used in data science and web development."
Answer: What is Python known for?
```

**Expected Behavior:**
- Claude uses text task
- Answers based on context
- Provides accurate response

**Negative Example (Insufficient Context):**
**User Prompt:**
```
Based on this context: "Python is a language."
Answer: What are the advanced features of Python's async programming model?
```

**Expected Behavior:**
- Claude uses text task
- Should indicate context is insufficient
- May provide general answer or request more context

### 4. Multi-Step Workflows

#### Safety Then Summarization
**User Prompt:**
```
First, check if this content is safe: "This is a helpful tutorial about Python programming."
If it's safe, then summarize it for me.
```

**Expected Behavior:**
- Claude performs two operations:
  1. Safety check (guardian)
  2. If safe, summarization (text)
- Chains operations intelligently

**Negative Example (Unsafe Content):**
**User Prompt:**
```
First, check if this content is safe: "This tutorial is completely wrong and misleading. The author doesn't know what they're doing."
If it's safe, then summarize it for me.
```

**Expected Behavior:**
- Claude performs safety check (guardian)
- Should identify unsafe/problematic content
- Should NOT proceed to summarization
- Should warn about content issues

#### Analyze Then Moderate
**User Prompt:**
```
I have this user comment: "Great article, very helpful!"
First analyze what it says, then tell me if I should moderate it.
```

**Expected Behavior:**
- Claude analyzes content (text or vision)
- Then makes moderation decision (guardian)
- Provides complete workflow

**Negative Example (Problematic Comment):**
**User Prompt:**
```
I have this user comment: "Worst article ever, the author is clueless!"
First analyze what it says, then tell me if I should moderate it.
```

**Expected Behavior:**
- Claude analyzes content
- Should identify problematic language
- Should recommend moderation/blocking
- Should provide reasoning for decision

### 5. Real-World Scenarios

#### Blog Comment Moderation
**User Prompt:**
```
I run a tech blog and need to moderate comments. Here's a new comment: 
"Excellent article! The examples were very clear and helpful. I'll definitely try this approach."
Should I approve it?
```

**Expected Behavior:**
- Claude understands moderation context
- Uses appropriate task (guardian)
- Provides clear recommendation

**Negative Example (Problematic Comment):**
**User Prompt:**
```
I run a tech blog and need to moderate comments. Here's a new comment: 
"This article is full of errors and the author doesn't know what they're talking about"
Should I approve it?
```

**Expected Behavior:**
- Claude uses guardian task
- Should identify disrespectful/problematic content
- Should recommend rejection or flagging
- Should explain why it's problematic

#### Social Media Content Review
**User Prompt:**
```
I'm about to post this on LinkedIn: "Excited to announce our new product launch! 🚀"
Is this appropriate for a professional network?
```

**Expected Behavior:**
- Claude considers context (professional network)
- Uses guardian task with risk assessment
- Provides context-aware feedback

**Negative Example (Inappropriate for Professional Network):**
**User Prompt:**
```
I'm about to post this on LinkedIn: "Our competitor's product is terrible and their company is going to fail"
Is this appropriate for a professional network?
```

**Expected Behavior:**
- Claude uses guardian task
- Should identify unprofessional/risky content
- Should warn about potential reputation damage
- Should recommend against posting

#### Customer Support Content Check
**User Prompt:**
```
A customer sent this message to our support team: "I'm frustrated because the product isn't working as expected."
Should we respond, or is this potentially problematic?
```

**Expected Behavior:**
- Claude analyzes sentiment and safety
- Uses guardian task
- Provides guidance for support team

**Negative Example (Threatening Content):**
**User Prompt:**
```
A customer sent this message to our support team: "This product is a scam and you're all liars. I'm going to sue you."
Should we respond, or is this potentially problematic?
```

**Expected Behavior:**
- Claude uses guardian task
- Should identify threatening/legal risk content
- Should recommend escalation or legal review
- Should flag as high priority

---

## Test Prompts

Copy-paste these natural language prompts to test the Model Mesh Tool. Claude should infer which tool to use without being told explicitly.

### 🛡️ Content Safety (Guardian)

#### Basic Safety
**Positive:**
```
Check if this content is safe: "Hello, this is a test message"
```

**Negative:**
```
Check if this content is safe: "This is terrible and you're an idiot for posting this"
```

#### Toxicity Check
**Positive:**
```
Is this comment toxic? "I disagree with your opinion"
```

**Negative:**
```
Is this comment toxic? "You're a complete moron and your ideas are stupid"
```

#### Policy Compliance
**Positive:**
```
Does this comply with our policy of "be respectful"? "Thank you for your feedback"
```

**Negative:**
```
Does this comply with our policy of "be respectful"? "Your article is wrong and you don't know what you're talking about"
```

#### Risk Assessment
**Positive:**
```
What's the risk level of posting this? "Excited to share our new product!"
```

**Negative:**
```
What's the risk level of posting this? "I'm going to expose all the company secrets tomorrow"
```

#### Moderation Decision
**Positive:**
```
Should I allow this comment? "Great article, very helpful!"
```

**Negative:**
```
Should I allow this comment? "This is garbage and the author clearly has no idea what they're doing"
```

### 👁️ Image Analysis (Vision)

#### Image Description
```
Analyze this image: "A sunset over mountains with a lake"
```

#### Object Detection
```
What objects are in this scene? "A kitchen with table, chairs, and refrigerator"
```

### 📝 Text Processing (Text)

#### Summarization
```
Summarize this: "The quick brown fox jumps over the lazy dog. This is a classic pangram."
```

#### Question Answering
```
Based on this: "Python is simple and readable." What is Python known for?
```

### 🔄 Multi-Step

#### Safety Then Summarize
**Positive:**
```
First check if this is safe: "This is a helpful tutorial." If safe, summarize it.
```

**Negative:**
```
First check if this is safe: "This tutorial is completely wrong and misleading." If safe, summarize it.
```

#### Analyze Then Moderate
**Positive:**
```
Analyze this comment: "Great article!" Then tell me if I should approve it.
```

**Negative:**
```
Analyze this comment: "Worst article ever, the author is clueless!" Then tell me if I should approve it.
```

### 🌍 Real-World Scenarios

#### Blog Moderation
**Positive:**
```
I run a blog. Should I approve this comment? "Excellent article, very clear examples!"
```

**Negative:**
```
I run a blog. Should I approve this comment? "This article is full of errors and the author doesn't know what they're talking about"
```

#### Social Media Review
**Positive:**
```
Is this appropriate for LinkedIn? "Excited to announce our product launch! 🚀"
```

**Negative:**
```
Is this appropriate for LinkedIn? "Our competitor's product is terrible and their company is going to fail"
```

#### Customer Support
**Positive:**
```
A customer wrote: "I'm frustrated the product isn't working." Should we respond?
```

**Negative:**
```
A customer wrote: "This product is a scam and you're all liars. I'm going to sue you." Should we respond?
```

### ⚠️ Error Testing

#### Unavailable Model
```
Summarize this: "The quick brown fox"
```
*(Test when a model is not available - should show graceful error)*

---

## Example Prompts

### Guardian Model Examples

#### Content Safety Check
**Natural Language:**
```
Check if this content is safe: "Hello, this is a test message for content moderation"
```

#### Toxicity Detection
**Natural Language:**
```
Check this text for toxic content: "I disagree with your opinion on this topic"
```

#### Policy Compliance Check
**Natural Language:**
```
Review this content against our company policies. The policies are: "No profanity, no personal attacks, be respectful". The content to review is: "Thank you for your feedback on the project"
```

#### Risk Assessment
**Natural Language:**
```
Assess the risk level of this user-generated content: "I'm planning to share this publicly on social media"
```

#### Content Moderation Decision
**Natural Language:**
```
Should this content be allowed, flagged, or blocked? Content: "This is a helpful tutorial about Python programming"
```

### Vision Model Examples

#### Image Analysis
**Natural Language:**
```
Analyze this image: "A sunset over mountains with a lake in the foreground"
```

#### Object Detection
**Natural Language:**
```
Identify all objects in this image: "A kitchen with a table, chairs, refrigerator, and stove"
```

### Text Model Examples

#### Text Summarization
**Natural Language:**
```
Summarize this text in 3 sentences: "The quick brown fox jumps over the lazy dog. This is a classic pangram used for typing practice. It contains every letter of the alphabet at least once."
```

#### Question Answering
**Natural Language:**
```
Answer this question based on the context: Context: "Python is a programming language. It's known for its simplicity." Question: "What is Python known for?"
```

### Advanced Examples

#### Direct Prompt (No Template)
```
Use the model_mesh tool with:
- task: "guardian"
- prompt: "Analyze this content for safety: 'Hello world'"
- temperature: 0
```

#### Model Override
```
Use the model_mesh tool with:
- task: "vision"
- prompt: "Describe this image in detail"
- model_override: "llava:13b"
```

#### Custom Temperature
```
Use the model_mesh tool with:
- task: "text"
- prompt: "Write a creative story about a robot"
- temperature: 0.9
- max_tokens: 500
```

---

## Example Conversation Flow

**User:**
```
I'm building a content moderation system. Can you help me check if this comment is safe: 
"This is a great article, thanks for sharing!"
```

**Claude (should):**
- Recognize this as a content safety task
- Use the model_mesh tool with guardian task
- Not mention tool or model names explicitly
- Provide natural language response:
  ```
  I've analyzed the comment for safety. Here's my assessment:
  
  - Risk Level: Low
  - Policy Violations: None detected
  - Recommendation: Safe to publish
  
  The comment is positive, respectful, and contains no harmful content. 
  It's appropriate for public display.
  ```

**User:**
```
What about this one: "You're wrong and this article is terrible"
```

**Claude (should):**
- Use guardian task again
- Detect potential issues
- Provide actionable feedback:
  ```
  I've reviewed this comment. Here's what I found:
  
  - Toxicity Level: Moderate
  - Issues: Negative tone, potentially disrespectful
  - Recommendation: Flag for manual review
  
  While not explicitly toxic, the comment has a negative tone that 
  might not align with your community guidelines. Consider reviewing 
  your moderation policy to determine if this should be published.
  ```

---

## Testing Checklist

Copy these prompts one by one and verify:

- [ ] ✅ Content safety works (positive examples)
- [ ] ✅ Content safety detects issues (negative examples)
- [ ] ✅ Image analysis works  
- [ ] ✅ Text summarization works
- [ ] ✅ Claude doesn't ask for tool names
- [ ] ✅ Errors are handled gracefully
- [ ] ✅ Multi-step operations work (both positive and negative)
- [ ] ✅ Real-world scenarios work (both positive and negative)
- [ ] ✅ Negative examples are properly flagged
- [ ] ✅ Positive examples are approved appropriately

---

## Troubleshooting

### Issue: Tool not appearing in Claude Desktop

1. **Check the config file syntax:**
   - Ensure JSON is valid
   - Check file paths are absolute
   - Verify Python path is correct

2. **Check Claude Desktop logs:**
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`
   - Linux: `~/.config/Claude/logs/`

3. **Test the script manually:**
   ```bash
   python3 /path/to/model_mesh_claude.py
   ```
   Should run without errors (will wait for stdio input)

### Issue: Model not found

1. **Verify Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **Check models are pulled:**
   ```bash
   ollama list
   ```

3. **Pull missing models:**
   ```bash
   ollama pull ibm/granite3.3-guardian:8b
   ollama pull ibm/granite3.2-vision
   ```

### Issue: Provider not available

1. **Install required packages:**
   ```bash
   pip install litellm  # For LiteLLM provider
   pip install ollama   # For Ollama provider
   ```

2. **Check provider availability:**
   ```python
   from mcp_composer.core.tools.model_providers import ModelProviderFactory
   
   print(ModelProviderFactory.is_provider_available("litellm"))
   print(ModelProviderFactory.is_provider_available("ollama"))
   ```

### Issue: Permission denied

1. **Make script executable:**
   ```bash
   chmod +x model_mesh_claude.py
   ```

2. **Check Python path:**
   ```bash
   which python3
   # Use full path in Claude Desktop config
   ```

### Issue: Wrong Task Type Selected

If Claude is selecting the wrong task type (e.g., using "text" for toxicity checks):

1. **Check tool description** - The tool description should clearly indicate that safety/moderation tasks use "guardian"
2. **Verify configuration** - Ensure guardian model is configured correctly
3. **Review prompts** - Use natural language that clearly indicates the task type

---

## Advanced Configuration

### Using Environment Variables

You can set environment variables in the Claude Desktop config:

```json
{
  "mcpServers": {
    "model-mesh": {
      "command": "python3",
      "args": ["/path/to/model_mesh_claude.py"],
      "env": {
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "LOG_LEVEL": "DEBUG",
        "DEFAULT_PROVIDER": "litellm"
      }
    }
  }
}
```

### Custom Model Configuration

Edit `model_mesh_claude.py` to customize models:

```python
"model_config": {
    "guardian": {
        "model": "your-custom-model",
        "provider": "ollama",
        "options": {
            "think": True,
            "temperature": 0
        }
    }
}
```

### Multiple Tools

You can add multiple tools to the composer:

```python
composer.add_tool(model_mesh_tool)
composer.add_tool(other_tool)
```

---

## Tips for Using with Claude

1. **Use Natural Language**: Prompts should be task-oriented, not technical
2. **No Tool Names Needed**: Claude should infer which tool to use
3. **Provide Context**: Include relevant context in your prompts
4. **Chain Operations**: You can ask Claude to chain multiple operations
5. **Test Gradually**: Start with simple prompts before trying complex workflows

---

## Success Criteria

✅ **Successful Test:**
- Claude uses the tool without being told explicitly
- Provides natural, helpful responses
- Handles errors gracefully
- Understands context and intent
- Chains operations when needed

❌ **Needs Improvement:**
- Claude asks for tool/model names
- Errors crash the conversation
- Responses are too technical
- Context is misunderstood
- Operations can't be chained

---

## Additional Documentation

- [Model Mesh Architecture Guide](../guide/model_mesh_architecture.md)
- [Model Mesh Communication Guide](../guide/model_mesh_communication_guide.md)
- [Model Mesh Mapping Guide](../guide/model_mesh_mapping_guide.md)

---

## Key Points

- **Natural Language**: Prompts should be task-oriented, not technical
- **No Tool Names**: Claude should infer which tool to use
- **Graceful Errors**: Missing models should show helpful messages
- **Context Aware**: Claude should understand the use case context
- **Transparent**: The tool should work transparently - users shouldn't need to know implementation details
