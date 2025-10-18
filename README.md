# SEO Audit Tool

An automated SEO analysis tool that uses Apify's SEO audit actor and Google's Gemini AI to provide comprehensive SEO recommendations.

## Features

- Automated SEO auditing using Apify
- AI-powered analysis with Google Gemini
- Detailed reporting of SEO issues and recommendations
- Local file caching to save API credits
- Environment variable configuration for secure credential management

## Prerequisites

- Python 3.x
- Apify API Token
- Google Gemini API Key

## Setup

1. Clone the repository:
```bash
git clone https://github.com/athxra/Agents
cd agents
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install apify-client google-generativeai python-dotenv
```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Add your API keys:
     ```
     APIFY_TOKEN=your_apify_token_here
     GEMINI_API_KEY=your_gemini_api_key_here
     ```

## Usage

1. Run the SEO audit:
```bash
python agent.py
```

2. Check the output:
   - SEO audit data will be saved in `seo_audit_page_*.json` files
   - Final report will be generated in `seo_fixes_report.txt`

## Output Files

- `seo_audit_page_*.json`: Raw SEO audit data from Apify
- `seo_fixes_report.txt`: AI-generated SEO recommendations and fixes

## Features in Development

- [x] JSON audit file processing
- [x] Enhanced summarization logic
- [x] Local file caching
- [ ] Improved error handling
- [ ] Comprehensive Gemini analysis
- [ ] Environment variable integration

## Contributing

Feel free to open issues or submit pull requests with improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
