from flask import Flask, render_template, request, Response
import threading
import queue
import urllib.error as urllib_err
import urllib.parse
import urllib.request

app = Flask(__name__)

threads = 5
user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:19.0) Gecko/20100101 Firefox/19.0"
target_url = "http://testphp.vulnweb.com"
wordlist_file = "all.txt"  # For demo purposes, you can upload a custom wordlist via HTML form
resume = None

def build_wordlist(wordlist_file):
    with open(wordlist_file, "rb") as fd:
        raw_words = fd.readlines()
    
    found_resume = False
    words = queue.Queue()
    
    for word in raw_words:
        word = word.rstrip()
        if resume is not None:
            if found_resume:
                words.put(word)
            else:
                if word == resume:
                    found_resume = True
                    print(f"Resuming wordlist from: {resume}")
        else:
            words.put(word)
    
    return words


def dir_bruter(word_queue, extensions=None, event_stream=None):
    while not word_queue.empty():
        attempt = word_queue.get()
        attempt_list = []

        # Check if there is a file extension; if not, it's a directory path
        attempt_str = attempt.decode('utf-8')

        if '.' not in attempt_str:
            attempt_list.append(f"/{attempt_str}/")
        else:
            attempt_list.append(f"/{attempt_str}")

        # If we want to bruteforce extensions
        if extensions:
            for extension in extensions:
                attempt_list.append(f"/{attempt_str}{extension}")

        # Iterate over our list of attempts        
        for brute in attempt_list:
            url = f"{target_url}{urllib.parse.quote(brute)}"
            try:
                headers = {"User-Agent": user_agent}
                r = urllib.request.Request(url, headers=headers)
                response = urllib.request.urlopen(r)
                if len(response.read()):
                    event_stream.put(f"[{response.code}] => {url}")
            except (urllib_err.HTTPError, urllib_err.URLError) as e:
                if e.code != 404:
                    event_stream.put(f"!!! {e.code} => {url}")
                else:
                    event_stream.put(f"!!! 404 => {url}")


def generate_sse(event_stream):
    while True:
        message = event_stream.get()
        yield f"data: {message}\n\n"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_brute_force', methods=['POST'])
def start_brute_force():
    url = request.form['url']
    wordlist = request.files['wordlist']
    wordlist_path = 'uploads/' + wordlist.filename
    wordlist.save(wordlist_path)

    word_queue = build_wordlist(wordlist_path)
    extensions = [".php", ".bak", ".orig", ".inc"]

    event_stream = queue.Queue()

    # Start the brute-force process in a separate thread
    def start_threads():
        for _ in range(threads):
            t = threading.Thread(target=dir_bruter, args=(word_queue, extensions, event_stream))
            t.start()

    start_threads()

    return "Brute-forcing started!"


@app.route('/stream_results')
def stream_results():
    event_stream = queue.Queue()

    def start_brute_force():
        word_queue = build_wordlist("uploads/all.txt")  # Example wordlist path
        extensions = [".php", ".bak", ".orig", ".inc"]
        dir_bruter(word_queue, extensions, event_stream)

    # Start the brute-force process in a separate thread for streaming
    threading.Thread(target=start_brute_force).start()

    return Response(generate_sse(event_stream), content_type='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
