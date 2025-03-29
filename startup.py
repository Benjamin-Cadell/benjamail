from main import benjamail

bm = benjamail(verbose=True)
bm.sort_emails(
    older_than_days = 14,
    test            = False,
    run_client      = True,
    max_emails      = 60,
    batch_size      = 30,
)
