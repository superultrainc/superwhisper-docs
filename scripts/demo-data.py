#!/usr/bin/env python3
"""Seed and remove fictional demo recordings for docs screenshots.

  scripts/demo-data.py seed      write 5 demo meetings and 10 demo dictations
  scripts/demo-data.py status    list what seed created and whether it exists
  scripts/demo-data.py remove    delete exactly the folders seed created

Writes into ~/Documents/superwhisper/recordings. Every folder it creates is
listed in a manifest outside the repo (~/.hermes/profiles/terry-t2/demo-data-manifest.json).
`remove` deletes only manifest entries whose meta.json still carries the demo marker
("demoData": true), so it cannot delete a real recording. Names, companies and
content are invented. Audio is macOS `say`, so no real voice is stored.
"""
import json, subprocess, sys, tempfile, wave, datetime as dt, shutil
from pathlib import Path

REC = Path.home() / "Documents/superwhisper/recordings"
MANIFEST = Path.home() / ".hermes/profiles/terry-t2/demo-data-manifest.json"
DB = Path.home() / "Library/Application Support/superwhisper/database/superwhisper.sqlite"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

VOICES = ["Samantha", "Daniel", "Karen", "Moira", "Alex"]

# (title, days_ago, hour_utc, speakers, private note, [(speaker idx, line)], summary)
MEETINGS = [
 ("Weekly product sync", 0, 14, ["You", "Priya", "Jordan"],
  "Ask Jordan about the export format.",
  [(0, "Okay, let's start with the launch checklist. Where are we on the release notes?"),
   (1, "Release notes are drafted. I still need a screenshot for the new settings page."),
   (2, "I can get you that by end of day. The build is stable on my machine."),
   (0, "Good. Do we want to ship Thursday or hold until next week?"),
   (1, "Thursday works if QA signs off tomorrow."),
   (2, "QA is on track. One open bug in the export flow, but it has a workaround."),
   (0, "Then we ship Thursday. Priya, please send the announcement draft to me on Wednesday.")],
  "## Summary\nThe team reviewed launch readiness and agreed to ship on Thursday.\n\n## Decisions\n- Ship the release on Thursday.\n- Hold the export bug fix for the next patch.\n\n## Action items\n- [ ] Priya: send the announcement draft on Wednesday\n- [ ] Jordan: share the settings page screenshot today\n- [ ] You: confirm QA sign-off tomorrow\n"),
 ("Design review: onboarding", 1, 16, ["You", "Maya", "Sam"],
  "Maya prefers the shorter flow.",
  [(1, "I cut the onboarding from six steps to four. The permissions step now comes first."),
   (0, "That is cleaner. Does the microphone prompt still appear at the right moment?"),
   (1, "Yes, right after the welcome screen. People see why we need it before the system dialog."),
   (2, "Can we test it with five new users before we commit?"),
   (0, "Let's do that. Sam, can you recruit the testers?"),
   (2, "Sure. I will have five lined up by Friday.")],
  "## Summary\nMaya presented a four step onboarding flow. The group agreed to test it before shipping.\n\n## Decisions\n- Move the permissions step to the start of onboarding.\n- Run a five person test before committing.\n\n## Action items\n- [ ] Sam: recruit five testers by Friday\n- [ ] Maya: share the prototype link\n"),
 ("Customer call: Acme Dental", 2, 15, ["You", "Alex Rivera"],
  "Acme has 12 seats. Wants invoices by email.",
  [(1, "We are a small dental office, twelve people. We mostly dictate patient notes."),
   (0, "Thanks for walking me through that. Do you need the notes to stay on the device?"),
   (1, "Yes, that matters a lot. We would rather nothing leave the office."),
   (0, "Then local models are the right fit. I can show you how to set that up for the whole team."),
   (1, "That would help. We also need invoices sent by email each month."),
   (0, "I will send you both today.")],
  "## Summary\nAcme Dental has 12 seats and needs local-only transcription for patient notes.\n\n## Decisions\n- Use local models for all seats.\n\n## Action items\n- [ ] You: send the local model setup guide today\n- [ ] You: set up monthly invoices by email\n"),
 ("Quarterly planning", 4, 18, ["You", "Jordan", "Priya", "Sam"],
  "Budget cap is a draft until Monday.",
  [(0, "Let's pick the three priorities for next quarter."),
   (1, "Reliability first. Crash rate is the number customers notice most."),
   (2, "I would add faster onboarding. It drives activation."),
   (3, "And documentation. Support keeps answering the same five questions."),
   (0, "Agreed. Reliability, onboarding, docs. Anything we drop to make room?"),
   (1, "We can pause the widget experiment."),
   (0, "Done. I will write this up and share it.")],
  "## Summary\nThe team chose three priorities for next quarter and paused one experiment.\n\n## Decisions\n- Priorities are reliability, onboarding and documentation.\n- Pause the widget experiment.\n\n## Action items\n- [ ] You: write up the plan and share it\n- [ ] Jordan: set a crash rate target\n"),
 ("One on one with Sam", 6, 17, ["You", "Sam"],
  "Talk about the conference talk.",
  [(1, "I would like to move toward more design work next quarter."),
   (0, "That makes sense. What would help you get there?"),
   (1, "Owning the onboarding project would be a good start."),
   (0, "I will propose that in planning. Also, are you still thinking about the conference talk?"),
   (1, "Yes. I would like to submit an abstract this month.")],
  "## Summary\nSam wants more design ownership and plans to submit a conference talk.\n\n## Decisions\n- Propose Sam as owner of the onboarding project.\n\n## Action items\n- [ ] You: raise the onboarding ownership in planning\n- [ ] Sam: submit the conference abstract this month\n"),
]

# (mode, app, days_ago, hour_utc, text)
DICTATIONS = [
 ("Message", "Slack", 0, 15, "Hey team, the new build is out. Please try the meeting notes and tell me what feels slow."),
 ("Mail", "Mail", 0, 16, "Hi Maya, thanks for the update. Could you send the revised timeline by Friday? Best, Nico."),
 ("Message", "Messages", 0, 17, "Running ten minutes late, start without me."),
 ("Note", "Notes", 1, 14, "Ideas for the demo. Show a quick dictation, then switch modes, then open the history."),
 ("Voice to text", "Safari", 1, 15, "How do I export a transcript as a text file from the history view?"),
 ("Mail", "Mail", 1, 19, "Hello Priya, I reviewed the draft and left comments in the document. The intro needs a stronger first line."),
 ("Message", "Slack", 2, 13, "Can someone review my pull request? It is a small change to the settings page."),
 ("Note", "Notes", 3, 16, "Grocery list. Oat milk, coffee beans, lemons, and a birthday card for Sam."),
 ("Super", "Cursor", 3, 18, "Write a function that takes a list of meeting titles and returns them sorted by date, newest first."),
 ("Message", "Messages", 5, 20, "Thanks for dinner last night. Let's do it again next month."),
]


def sh(*a):
    subprocess.run(a, check=True, capture_output=True)


def say_wav(text, voice, out):
    with tempfile.TemporaryDirectory() as d:
        aiff = Path(d) / "x.aiff"
        sh("say", "-v", voice, "-o", str(aiff), text)
        sh("afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(out))


def wav_len(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def join_wavs(parts, out, gap=0.6):
    with wave.open(str(parts[0])) as w:
        params = w.getparams()
    silence = b"\x00\x00" * int(params.framerate * gap)
    with wave.open(str(out), "wb") as o:
        o.setparams(params)
        for p in parts:
            with wave.open(str(p)) as w:
                o.writeframes(w.readframes(w.getnframes()))
            o.writeframes(silence)


def when(days_ago, hour):
    t = (NOW - dt.timedelta(days=days_ago)).replace(hour=hour, minute=17, second=0)
    return t if t <= NOW else t - dt.timedelta(days=1)


def folder_for(t, taken):
    n = int(t.timestamp())
    while str(n) in taken or (REC / str(n)).exists():
        n += 1
    return str(n)


def base(t, kind, mode, dur_ms, text):
    return {
        "appVersion": "3.0.1", "demoData": True, "kind": kind, "modeName": mode,
        "datetime": t.strftime("%Y-%m-%dT%H:%M:%S"), "duration": dur_ms,
        "modelKey": "sv-1", "modelName": "S1-Voice (Cloud)",
        "languageModelKey": "sl-1", "languageModelName": "S1-Language",
        "processingTime": 420, "languageModelProcessingTime": 380,
        "languageSelected": "en", "recordingDevice": "BuiltInMicrophoneDevice",
        "rawResult": text, "result": text, "llmResult": text, "prompt": "",
        "realtimeEnabled": False, "translationEnabled": False,
        "applicationContextEnabled": False, "literalPunctuationEnabled": False,
        "separateSpeakersEnabled": False, "systemAudioEnabled": False, "speakers": [],
    }


def seed():
    if MANIFEST.exists():
        sys.exit("manifest exists. Run `remove` first.")
    if not REC.is_dir():
        sys.exit(f"no recordings folder: {REC}")
    made, taken = [], set()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for title, days, hr, names, note, lines, summary in MEETINGS:
            t = when(days, hr)
            fid = folder_for(t, taken); taken.add(fid)
            parts, segs, cursor = [], [], 1.0
            for i, (spk, text) in enumerate(lines):
                p = tmp / f"{fid}-{i}.wav"
                say_wav(text, VOICES[spk % len(VOICES)], p)
                n = wav_len(p)
                segs.append({"speaker": spk, "start": round(cursor, 3), "end": round(cursor + n, 3),
                             "text": text, "words": []})
                cursor += n + 0.6
                parts.append(p)
            d = REC / fid
            d.mkdir()
            made.append(fid)
            join_wavs(parts, d / "output.wav")
            full = " ".join(s["text"] for s in segs)
            m = base(t, "meeting", "Meeting", int(cursor * 1000), full)
            m.update(title=title, segments=segs, llmResult=summary, privateNotes=note,
                     speakers=[{"number": i, "name": n} for i, n in enumerate(names)],
                     separateSpeakersEnabled=True, systemAudioEnabled=True,
                     attendees=[], appVersion="3.0.1")
            (d / "meta.json").write_text(json.dumps(m, indent=2))
        for mode, app, days, hr, text in DICTATIONS:
            t = when(days, hr) + dt.timedelta(minutes=len(made))
            fid = folder_for(t, taken); taken.add(fid)
            d = REC / fid
            d.mkdir()
            made.append(fid)
            say_wav(text, "Samantha", d / "output.wav")
            dur = wav_len(d / "output.wav")
            m = base(t, "dictation", mode, int(dur * 1000), text)
            m["segments"] = [{"start": 0.3, "end": round(dur, 3), "text": text}]
            m["promptContext"] = {"systemContext": {"language": "English", "time": t.strftime("%B %d, %Y at %I:%M %p"),
                                                    "timezone": "UTC", "locale": "en_US"},
                                  "applicationContext": {"name": app, "nouns": [], "includeInPrompt": False},
                                  "userContext": {}, "modeContext": {"type": "message", "language": "en", "examples": []}}
            (d / "meta.json").write_text(json.dumps(m, indent=2))
    MANIFEST.write_text(json.dumps({"created": dt.datetime.now().isoformat(), "folders": made}, indent=2))
    print(f"seeded {len(made)} folders: {', '.join(made)}")


def load():
    if not MANIFEST.exists():
        sys.exit("no manifest: nothing seeded")
    return json.loads(MANIFEST.read_text())["folders"]


def status():
    for f in load():
        p = REC / f / "meta.json"
        if p.exists():
            m = json.loads(p.read_text())
            print(f"{f}  {m['kind']:<9} {m.get('title') or m['modeName']:<30} demo={m.get('demoData')}")
        else:
            print(f"{f}  missing")


def remove():
    gone = 0
    for f in load():
        d = REC / f
        p = d / "meta.json"
        if not p.exists():
            continue
        if not json.loads(p.read_text()).get("demoData"):
            print(f"SKIP {f}: no demo marker"); continue
        # the app may have rewritten meta.json and dropped the marker; the manifest is the second guard
        shutil.rmtree(d); gone += 1
    MANIFEST.unlink()
    print(f"removed {gone} folders. If the app still lists them, restart Superwhisper.")


if __name__ == "__main__":
    {"seed": seed, "status": status, "remove": remove}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
