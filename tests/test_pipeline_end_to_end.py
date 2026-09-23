import pytest

from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')


def test_run_evaluation_pipeline_and_format_verdict(monkeypatch):
    """Run the pipeline with mocked backend tools and a mocked LLM client."""
    summary_text = 'This company has a stable tech stack and moderate signals.'
    verdict_text = (
        'VERDICT: DEPRIORITIZE\n'
        'REASONING: Funding stage and hiring activity are not aligned with the target ICP. Some signals indicate a smaller, cost-conscious business.\n'
        'KEY SIGNALS:\n'
        '- Funding stage mismatch (web search / fundamentals)\n'
        '- No strong hiring signals for ICP roles\n'
        '- Technology signals show legacy ERP and low cloud adoption\n'
    )

    monkeypatch.setattr('backend.agent.pipeline.get_tech_signals', lambda company_name: {
        'raw_data': {'company_name': company_name, 'technologies': ['ERP']},
        'summary': 'Technology summary placeholder.',
    })

    monkeypatch.setattr('backend.agent.pipeline.get_hiring_signals', lambda company_name: {
        'raw_data': {'company_name': company_name, 'roles': ['Operations']},
        'summary': 'Hiring summary placeholder.',
    })

    monkeypatch.setattr('backend.agent.pipeline.get_web_search_data', lambda company_name: {
        'raw_data': {
            'fundamentals': {'company_name': company_name, 'funding_stage': 'Seed'},
            'news': {'headline': 'Recent market update'},
            'company_signals': {
                'funding_stage': 'Seed',
                'headcount_range': '50-100',
                'founded_year': '2019',
                'headquarters': 'Austin, TX',
                'revenue_estimate': '$5M-$10M',
            },
        },
        'summary': 'Web search summary placeholder.',
    })

    monkeypatch.setattr('backend.agent.pipeline._summarize_tool_result', lambda result, tool_name, system_prompt: summary_text)
    monkeypatch.setattr('backend.agent.pipeline._generate_verdict', lambda *args, **kwargs: {
        'raw_text': verdict_text,
        'decision': 'DEPRIORITIZE',
        'reasoning': 'Funding stage and hiring activity are not aligned with the target ICP. Some signals indicate a smaller, cost-conscious business.',
        'signals': [
            'Funding stage mismatch (web search / fundamentals)',
            'No strong hiring signals for ICP roles',
            'Technology signals show legacy ERP and low cloud adoption',
        ],
    })

    result = run_evaluation_pipeline(
        company_name='Test Company',
        icp_profile={
            'target_company_size': '100-1000',
            'funding_stage': ['Series A'],
            'tech_signals': ['ERP'],
            'hiring_signals': ['Operations'],
            'budget_indicator': 'mid-market',
            'raw_description': 'B2B logistics intelligence platform',
        }
    )

    assert result['company_name'] == 'Test Company'
    assert result['verdict']['decision'] == 'DEPRIORITIZE'
    assert result['technology']['summary'] == summary_text
    assert result['hiring']['summary'] == summary_text
    assert result['web_search']['summary'] == f"{summary_text}\n\n{summary_text}"

    formatted = format_verdict_display(result['verdict'])
    assert formatted['decision'] == 'DEPRIORITIZE'
    assert formatted['signals'][0] == 'Funding stage mismatch (web search / fundamentals)'
