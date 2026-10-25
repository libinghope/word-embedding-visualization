"""Explicit download command. Never called from API, tests, or the build script."""
import argparse
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="word2vec-google-news-300")
    args = parser.parse_args()
    import gensim.downloader as api
    last_report = [0.0]
    def progress(count, block_size, total_size):
        now = time.monotonic()
        if now - last_report[0] >= 5:
            done = count * block_size
            print(f'Downloaded {done / 1024**2:.1f} / {total_size / 1024**2:.1f} MiB', flush=True)
            last_report[0] = now
    api._progress = progress
    print(api.load(args.model, return_path=True))

