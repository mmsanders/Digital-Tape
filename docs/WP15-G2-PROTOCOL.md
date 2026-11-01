# WP-15 G2 — unaided test protocol

**Issued by PM627, 29 October 2026 PDT ([ADR-196](DECISIONS.md#adr-196--c1-disposed-phase-2-at-1112-c2-and-g2-queued)).**
Criterion ([WP-15 G2](PACKAGES/WP-15.md)): the D6 tester, with no instructions beyond what the app
shows, makes a cartridge from a folder Michael provides. `tapectl verify` passes and `dump` plays
it correctly. One attempt, under 10 minutes excluding load time. Michael witnesses and records the
outcome and every point where the tester hesitated. G2 is Michael's witnessed record. PM checks
it against this protocol; Verification does not sign it.

**When:** after Verification #370 passes C2 on the exact candidate. Use that same ZIP. A rebuilt
candidate needs its own C2 clearance first.

## Before she sits down (Michael alone)

1. The extracted cleared candidate is on the desktop, with `digital-tape.exe` reachable by
   double-click. The app is closed.
2. The music folder is on the desktop: under 60 minutes, songs only, no subfolders. Don't use the
   C2 folders.
3. One PNY card is **out of the reader**, next to the reader, which is plugged in. No other
   removable drives are attached. The card may hold anything: the app replaces it.
4. **UAC:** use an account where she can approve the prompt herself (an administrator account,
   prompt shows Yes/No). If the only option is a credential prompt she can't answer, decide before
   starting: you may type the password **only when she asks**, and you record it as an assist.
5. Have a phone timer ready, and paper or a phone note for hesitations.

## What you may say

Say only this, once: **"Please use Digital Tape to put the music in this folder onto this card.
Give it any name you like."** Point at the app, the folder and the card. Don't explain drag and
drop, labels, cards, Replace or the UAC prompt. If she asks a question, say "Do whatever you
think is right." Don't touch the computer. Stopping her to prevent harm to *other* disks is
always allowed; it ends the attempt.

## What to record

- Times: start (she touches the computer), Make pressed, UAC approved, "Your cartridge is ready",
  end. **Load time** is from UAC approval to "ready". It is excluded from the 10 minutes.
- Every hesitation: a pause over about 5 seconds, a wrong click, a question, a re-read of the
  screen. Note where she was and what she seemed to look for.
- Any error message she saw, and what she did next.
- Her own words afterwards: what was confusing, if anything.

## Checking the cartridge (Michael, after she is done)

Run section 3 of the C2 checklist (`verify`, `dump --side A`, `dump --side B`) with `G2-`
filenames. Then play the start of `G2-A.wav`, one join between two songs, and the end, on
ordinary speakers. Expect no clicks at the joins and the songs in folder order.

## Result

**PASS** needs all of these:
- one attempt;
- no assist (or only a recorded password entry, which PM judges);
- under 10 minutes excluding load time;
- verify `OK`, exit 0;
- the dump plays correctly.

Otherwise record what happened. Don't retry with the same tester. If G2 fails, PM decides any fix.
A second G2 needs a tester who hasn't seen the app (D6 fallback).

Return everything on the G2 issue PM posts:
- the times;
- the hesitation notes;
- screenshots if taken;
- the verify/dump text files and hashes;
- your judgement of each PASS condition.
