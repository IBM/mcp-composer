# Installation Guide

## Quick Install

```bash
# 1. Clone the repository
git clone <repository-url>
cd mcp-tools-audit

# 2. Install Bob Skills (REQUIRED for auditing)
cp -r bob-skills ~/.bob/skills/tool-audit

# 3. Verify installation
ls ~/.bob/skills/tool-audit
```

## Detailed Installation Steps

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd mcp-tools-audit
```

### Step 2: Install Bob Skills

**This step is REQUIRED to use the tool audit functionality with Bob AI.**

The Bob skills must be copied to your local Bob skills directory:

```bash
cp -r bob-skills ~/.bob/skills/tool-audit
```

**What this does:**
- Copies all skill files to `~/.bob/skills/tool-audit/`
- Makes the `tool-audit` skill available in Bob's Advanced mode
- Enables Bob to perform comprehensive tool audits

**Verify the installation:**
```bash
ls ~/.bob/skills/tool-audit
```

You should see:
```
SKILL.md
README.md
QUICK-START.md
analysis-techniques.md
report-template.md
quality-checklist.md
example-analysis.md
```

### Step 3: (Optional) Set Up Environment Variables

If you need to authenticate with IBM Cloud services:

```bash
cp .env.example .env
```

Edit `.env` and add your IBM Cloud API key:
```bash
IBM_CLOUD_API_KEY=your_api_key_here
```

**Get your API key:**
1. Log in to [IBM Cloud](https://cloud.ibm.com)
2. Navigate to **Manage** → **Access (IAM)** → **API keys**
3. Click **Create an IBM Cloud API key**
4. Copy and save the key securely

### Step 4: Test the Installation

**Test the script:**
```bash
python3 list_all_tools.py --help
```

**Test Bob skills:**
1. Open Bob AI
2. Switch to **Advanced mode** (skills only work in Advanced mode)
3. Say: "Use the tool-audit skill"
4. Bob should recognize the skill

## Troubleshooting

### Issue: Bob doesn't recognize the skill

**Solution:**
1. Verify the files are in the correct location:
   ```bash
   ls ~/.bob/skills/tool-audit/SKILL.md
   ```
2. Make sure you're in **Advanced mode** (not Code, Ask, or Plan mode)
3. Try restarting Bob

### Issue: Permission denied when copying files

**Solution:**
```bash
# Create the directory first if it doesn't exist
mkdir -p ~/.bob/skills/tool-audit
# Then copy with sudo if needed
sudo cp -r bob-skills/* ~/.bob/skills/tool-audit/
```

### Issue: Script can't find Python

**Solution:**
```bash
# Check Python version
python3 --version
# Should be 3.7 or higher

# If not installed, install Python 3
# macOS:
brew install python3
# Ubuntu/Debian:
sudo apt-get install python3
```

## Updating the Skills

To update to the latest version:

```bash
# Pull latest changes
cd mcp-tools-audit
git pull

# Update Bob skills
cp -r bob-skills ~/.bob/skills/tool-audit
```

## Uninstalling

To remove the Bob skills:

```bash
rm -rf ~/.bob/skills/tool-audit
```

## Next Steps

After installation:
1. Read the [README.md](README.md) for usage instructions
2. Check [bob-skills/QUICK-START.md](bob-skills/QUICK-START.md) for a quick guide
3. Run your first audit following the [Example Workflow](README.md#example-workflow)

## Support

If you encounter issues:
1. Check this installation guide
2. Review the [README.md](README.md) troubleshooting section
3. Verify you're using Bob in Advanced mode
4. Check that all files were copied correctly