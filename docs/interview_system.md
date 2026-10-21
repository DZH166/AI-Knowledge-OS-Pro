# Interview System

The mock interview system is planned for V4.0. Current support is documentation and learning artifact text, not a full interview product module.

## Existing Baseline

- Chat answer mode includes interview expression.
- Learning artifacts can include interview expression content.
- `docs/resume_pitch.md` and `docs/interview_qa.md` support manual interview preparation.

## Target Models

- `InterviewSession`
- `InterviewQuestion`
- `InterviewAnswer`
- `InterviewFeedback`

## Target Page

```text
/interview
```

## Target Flow

```text
Select topic
-> generate or choose question
-> user answers
-> provider-backed feedback if configured
-> save weak points
-> generate review cards
```

## Provider Rule

Demo mode may show sample questions. Real personalized feedback requires an LLM provider and must refuse when the provider is missing.

## Current Status

- Dedicated API: missing.
- Dedicated UI: missing.
- Persistence models: missing.
- Documentation: present as a V4.0 target.
