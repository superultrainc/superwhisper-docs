# Superwhisper mode file format

A mode is one JSON file in `<superwhisper-folder>/modes/`, and its `key` must also be appended to the `modeKeys` array in `<superwhisper-folder>/settings/settings.json` — the app only loads registered modes. `settings.json` also holds `vocabulary` and `replacements`, so edit it carefully and preserve everything you don't mean to change.

The schema below is taken from real mode files. Before writing anything, read one of the user's existing mode files — if their files have fields not listed here, preserve that shape.

## Fields that matter

| Field | What it does |
| --- | --- |
| `key` | Unique ID. Must equal the filename without `.json` AND be appended to `modeKeys` in settings.json. Convention: `<type>-XXXX` with 4 random uppercase letters (`custom-KQRT`). The plain built-ins use bare keys (`custom`, `super`). |
| `name` | Display name in the Modes list. |
| `type` | `"message"`, `"custom"`, `"super"`, or `"voice"`. Use `custom` for anything with your own prompt. |
| `prompt` | The AI instructions (custom modes). Empty for built-in types. |
| `tone` | Message modes only: `"casual"`, `"semi-formal"`, or `"formal"`. |
| `language` | `"en"` or another code; `"auto"` for automatic. |
| `voiceModelID` | Transcription model. Copy a value from the user's existing modes (e.g. `sv-1` = S1-Voice, `cohere-transcribe-q4` = Cohere Transcribe). |
| `languageModelID` | AI model. Copy from existing modes (e.g. `sl-1` = S1-Language). |
| `contextFromSelection` | `true` sends the selected text to the AI. |
| `contextFromClipboard` | `true` sends recently copied text. |
| `contextFromActiveApplication` | `true` sends the active app's visible text/context. |
| `diarize` | Speaker separation. Leave `false` unless asked. |
| `useSystemAudio` | Record what the computer plays. Leave `false` unless asked. |

`activationApps` / `activationSites` auto-activate the mode in specific apps (`["Slack", "Mail"]`) or sites (`["mail.google.com", "claude.ai"]`) — use them for workflow-specific modes.

Boilerplate to copy through unchanged from an existing file: `autocapitalizeInsert`, `contextTemplate`, `description`, `iconName`, `literalPunctuation`, `promptExamples`, `realtimeOutput`, `script`, `scriptEnabled`, `translateToEnglish`, `version`.

## Minimal custom mode

```json
{
  "activationApps": [],
  "activationSites": [],
  "autocapitalizeInsert": true,
  "contextFromActiveApplication": false,
  "contextFromClipboard": false,
  "contextFromSelection": false,
  "contextTemplate": "Use the copied text as context to complete this task.\n\nCopied text: ",
  "description": "",
  "diarize": false,
  "iconName": "",
  "key": "custom-XXXX",
  "language": "en",
  "languageModelID": "<copy from existing mode>",
  "literalPunctuation": false,
  "name": "<name>",
  "prompt": "<instructions>",
  "promptExamples": [],
  "realtimeOutput": false,
  "script": "",
  "scriptEnabled": false,
  "tone": "semi-formal",
  "translateToEnglish": false,
  "type": "custom",
  "useSystemAudio": false,
  "version": 1,
  "voiceModelID": "<copy from existing mode>"
}
```

## Templates

Personalize every prompt with what Step 1 taught you about the user's voice. The structure below works; the "My voice" section must be rewritten per user. Beyond these three, build workflow modes the history justifies (an email mode auto-activated in mail apps, an AI-prompt mode auto-activated in agent/chat apps that preserves technical terms literally and never answers the prompt itself) using the same custom-mode pattern.

### Write for me

`type: custom`, `contextFromSelection: true`, `contextFromActiveApplication: true`, `iconName: "star.fill"`.

Prompt structure (adapt, don't copy verbatim):

```text
You are my scribe. Turn intent into finished, ready-to-send text — never
transcribe my words literally. The User Message is a brief, not the text to
output.

If text is selected, treat my message as an edit command and rewrite the Text
Selection Context. Otherwise, draft a new message from my intent.

Match format to the app (Application Context): email → greeting + sign-off;
chat → short, neither; docs → clean prose.

My voice: <2-4 lines describing the user's actual style, from their history:
sentence length, contractions, formality, phrases they use, words they never
use>.

Output only the finished text, ready to paste — no preamble, no options, no
quotes. Match length to the intent.
```

Add 2-3 `Intent → Output` examples inside the prompt, written in the user's voice and about the user's actual topics.

### Message

`type: message` — the built-in Message preset needs no prompt. Set `tone` to match the user ("casual" / "semi-formal" / "formal") and leave `prompt` empty. Only build a custom-type message mode if the user wants behavior the tone slider can't express.

### Format selected text

`type: custom`, `contextFromSelection: true`, `iconName: "bolt.fill"`.

```text
The Text Selection Context is the text to transform. The User Message is the
instruction (e.g. "make this shorter", "fix the grammar", "make it friendly").

Apply the instruction to the selected text. Preserve meaning, formatting, and
markdown unless the instruction says otherwise. If no instruction was given,
clean the text up: fix grammar, spelling, and punctuation without changing
the tone.

Output only the rewritten text — no commentary, no quotes, no preamble.
```
