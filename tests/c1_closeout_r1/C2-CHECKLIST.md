# C2: make a cartridge on Windows 11 (about 45 minutes)

Use this only after Verification posts **C2 clearance of an exact head and ZIP**
in [Verification364](https://github.com/mmsanders/digital-tape-verification/issues/364).
Copy that return's download link and four hashes into your notes. A newer build
needs its own clearance. This checklist does not authorize an uncleared candidate.

You need your Windows 11 computer, reader, **one expendable PNY card**, and a short
folder of music (about 1–2 minutes keeps the session short). The app replaces the
whole card. Remove other removable drives first. Keep your original music folder.
Have a second folder containing over 60 minutes of music, a folder containing an
ordinary text file, and one individual song file ready. Don't show the app to your
wife yet; her unaided test is later.

## 1. Install and record (5 minutes)

1. Download the cleared candidate ZIP, open PowerShell in its download folder and run
   `Get-FileHash .\Digital-Tape-Windows11-x64-make-candidate.zip -Algorithm SHA256`.
   Compare with the clearance. Extract to a new folder. Hash `digital-tape.exe`,
   `tapectl.exe` and `ingest.exe` there with `Get-FileHash`; save the four results.
   Stop and return the mismatch if any differ.
2. Press Windows+R, type `winver`, and photograph/screenshot the version and OS build.
   Note whether your Windows account is an administrator or standard account.
3. Double-click `digital-tape.exe` normally. Do not choose Run as administrator.
   If Windows blocks it, record the screen and stop; don't change security policy.
   Record any prompt before the window opens. App/ingest must not request UAC.
4. With no card inserted, capture the Empty window: drop area, zero length bar,
   blank label, "Put a card in.", and disabled Make cartridge. There should be one
   app window and no lists of songs, files, folders or cards, player or library.

## 2. Common path and erase decline (10 minutes)

1. Insert only the expendable PNY card. Expect "Card ready" with its size, no picker.
2. Drop your short music **folder**. Expect "Checking the music…", then the length
   bar. Type a label such as `C2 MUSIC`. Make should enable only after the check,
   label and single card are ready. Capture Ready. Keep editing the label while
   card discovery updates; the text and caret should stay where you put them.
3. Press Make cartridge. Photograph the erase modal. Choose **Keep card** once:
   no UAC, no make, no automatic retry. Press Make again and choose **Replace**.
4. Record the UAC prompt text/publisher and confirm that it identifies **tapectl**,
   not the app or ingest. Approve it. Expect one prompt for this Make, then one
   progress bar and a plain step line. Capture Making. Don't pull the card yet.
5. Try closing the app while Making: expect "Wait until the cartridge is finished."
   Wait for "Your cartridge is ready. You can take the card out now." Capture Done.
   Note any console windows, unexpected prompt, stall, backwards bar or error.

## 3. Check the actual cartridge (5 minutes)

From the extracted candidate folder, open PowerShell **as administrator** for these
manual CLI checks only. Identify the inserted PNY by capacity/model in Disk Management;
do not guess its disk number. Set `$cardPath` to its actual `\\.\PhysicalDriveN`.
Use that same path below. These commands read the card; do not run provision/load.

```powershell
$cardPath = '\\.\PhysicalDriveN' # replace N with the PNY's actual disk number
.\tapectl.exe verify $cardPath *> C2-verify.txt
"exit=$LASTEXITCODE" | Add-Content C2-verify.txt
.\tapectl.exe dump $cardPath --side A -o C2-A.wav *> C2-dump-A.txt
"exit=$LASTEXITCODE" | Add-Content C2-dump-A.txt
.\tapectl.exe dump $cardPath --side B -o C2-B.wav *> C2-dump-B.txt
"exit=$LASTEXITCODE" | Add-Content C2-dump-B.txt
Get-FileHash C2-A.wav,C2-B.wav -Algorithm SHA256 | Out-File C2-dump-hashes.txt
Get-Item C2-A.wav,C2-B.wav | Select-Object Name,Length | Out-File C2-dump-lengths.txt
```

Expect verify `OK` and exit 0 for all three commands, identical A/B dump lengths
and hashes. Keep the WAVs locally in case a failure needs examination; return the
text files first. Close the elevated console; continue using the normal app.

## 4. Person-triggerable problems (10 minutes)

Start over between each input case. Capture the sentence and Show details each time.
Select/copy some details text to show it is copyable; ordinary card polling should
not close that view or erase an unrelated music error.

1. Drop the individual song file: folders-only message, nothing added.
2. Drop the over-60-minute folder: exact "too long" sentence, full too-long bar,
   Make disabled. Record the stated minutes/seconds.
3. Drop the folder with the text file: identifies the folder as containing nonmusic,
   no successful check or Make. A corrupt-song fixture, if already available, should
   identify that song as unusable. Don't buy or seek protected music for this test.
4. Ready the short valid folder and card again. Press Make, Replace, then **No** on
   UAC (cancel credentials on a standard account). Expect "The computer said no,
   so the card wasn't changed…", no make/progress/automatic retry. Capture it.
5. If convenient, remove the card while the erase modal is open, then press Replace.
   Expect current card-line guidance, no UAC or make. Reinsert it before continuing.

## 5. One pull, then remake (10 minutes)

1. With the short valid folder ready, make again and approve UAC. Once the step says
   loading/writing (not while Checking or in the confirmation), **pull the PNY once**.
   Expect the card-interrupted sentence and no automatic restart. Capture it and
   its Show details. Note the visible step and when you pulled. Don't infer that
   the partially written card is unchanged or usable.
2. Reinsert the same card, reset/re-drop the short folder if needed, and make again.
   One new UAC prompt is expected. Wait for Done. Repeat step 3's verify/dump checks
   with `C2-remake-` filenames so the first results are kept.
3. Capture the final screen and close the app normally. If anything failed, return
   what happened and the exact message; don't repeat the pull or improvise repairs.

## Return

Reply on Verification364 with: cleared head, four hashes, OS screenshot/build,
card/reader model, account type, prompt text, pass/fail or unrun for each numbered
section, time taken, and the screenshots and CLI text files. Say which normal UI
states you saw: Empty, Ready, Making, Done/Problem; whether there were any lists,
extra windows or console flashes; and whether label editing/details stayed usable.
Do not send your music. Missing observations remain unrun, not presumed passes.
Verification uses these observations with CI for G1/G3/G4/G5; G2 is still separate.
