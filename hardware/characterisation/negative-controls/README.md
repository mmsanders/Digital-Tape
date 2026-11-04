Negative-control judges for independent suites. Not the judge; never edit.

media_atomicity_baf176c.py is the judge at PR #646 commit baf176c, Git blob
3c85cda2db275ce2fd8445ff3af3e260d2062197, kept byte-for-byte. Verification
rig_cli_review_r1 needs it as --negative-judge: it must pass the valid run and fail
both deep-JSON cases. The hardware CI checkout is shallow, so it cannot be read from
history at test time.
