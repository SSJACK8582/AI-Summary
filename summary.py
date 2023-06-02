import os
import re
import json
import time
import requests
from dotenv import load_dotenv
from gevent import pywsgi
from flask import Flask, request, Response
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
CORS(app)
data_path = 'audio'
headers = {'cookie': os.getenv('cookie')}
html = '''
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>AI Summary</title>
    <script src="https://unpkg.com/react@16/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@16/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/babel-standalone@6/babel.min.js"></script>
    <script src="https://unpkg.com/moment@2/moment.js"></script>
    <script src="https://unpkg.com/antd@4/dist/antd.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/antd@4/dist/antd.min.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="text/babel">
      function MyApp() {
        const [inputValue, setInputValue] = React.useState("");
        const [cardTitle, setCardTitle] = React.useState("");
        const [cardContent, setCardContent] = React.useState("");
        const [loading, setLoading] = React.useState(false);
        const readStream = (reader) => {
          reader.read().then(({ done, value }) => {
            if (done) return;
            setCardContent((data) => data + new TextDecoder().decode(value));
            readStream(reader);
          });
        };
        const handleClick = async (value) => {
          setLoading(true);
          const response1 = await fetch(
            window.location.href + "title",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ url: value }),
            }
          );
          const text = await response1.text();
          setCardTitle(text);
          setCardContent("");
          const response2 = await fetch(
            window.location.href + "api",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ url: value }),
            }
          );
          const stream = response2.body;
          const reader = stream.getReader();
          readStream(reader);
          setLoading(false);
        };
        return (
          <div className="App" style={{ textAlign: "center" }}>
            <antd.Layout>
              <antd.Layout.Content style={{ padding: "5%" }}>
                <antd.Typography.Title>一键总结B站视频</antd.Typography.Title>
                <antd.Space.Compact style={{ width: "100%", padding: "5%" }}>
                  <antd.Input
                    placeholder="输入视频链接"
                    onChange={(e) => setInputValue(e.target.value)}
                  />
                  <antd.Button
                    type="primary"
                    onClick={() => handleClick(inputValue)}
                  >
                    一键总结
                  </antd.Button>
                </antd.Space.Compact>
                <antd.Space direction="vertical" style={{ width: "90%" }}>
                  <antd.Card title={cardTitle}>
                    {loading ? (
                      <antd.Spin />
                    ) : (
                      <div
                        style={{ textAlign: "left", whiteSpace: "pre-line" }}
                      >
                        {cardContent}
                      </div>
                    )}
                  </antd.Card>
                </antd.Space>
              </antd.Layout.Content>
              <antd.Layout.Footer>
                <antd.Typography.Link
                  href="https://github.com/SSJACK8582"
                  target="_blank"
                >
                  Code By JACK
                </antd.Typography.Link>
              </antd.Layout.Footer>
            </antd.Layout>
          </div>
        );
      }
      ReactDOM.render(<MyApp />, document.getElementById("root"));
    </script>
  </body>
</html>
'''


def get_view_data(id):
    if id.startswith('av'):
        url = 'https://api.bilibili.com/x/web-interface/view?aid={}'.format(id[2:])
    else:
        url = 'https://api.bilibili.com/x/web-interface/view?bvid={}'.format(id)
    try:
        resp = requests.get(url=url, headers=headers)
        resp_json = json.loads(resp.text)
        return resp_json.get('data', {})
    except Exception as e:
        print(e)


def get_play_data(id, cid):
    if id.startswith('av'):
        url = 'https://api.bilibili.com/x/player/v2?aid={}&cid={}'.format(id[2:], cid)
    else:
        url = 'https://api.bilibili.com/x/player/v2?bvid={}&cid={}'.format(id, cid)
    try:
        resp = requests.get(url=url, headers=headers)
        resp_json = json.loads(resp.text)
        return resp_json.get('data', {})
    except Exception as e:
        print(e)


def get_subtitle_list(id, p):
    view_data = get_view_data(id)
    title = view_data.get('title')
    print(id, title)
    if p and p != 1:
        pages = view_data.get('pages')
        for page in pages:
            if p == page.get('page'):
                cid = page.get('cid')
                play_data = get_play_data(id, cid)
                return play_data.get('subtitle', {}).get('subtitles', [])
    else:
        return view_data.get('subtitle', {}).get('list', [])


def get_subtitle_url(subtitle_list):
    for subtitle in subtitle_list:
        subtitle_url = subtitle.get('subtitle_url')
        if subtitle_url.startswith('//'):
            return 'http:' + subtitle_url
        else:
            return subtitle_url


def format_duration(duration):
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    if hours > 0:
        return '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
    else:
        return '{:02d}:{:02d}'.format(minutes, seconds)


def get_subtitle_content(subtitle_url):
    result = []
    try:
        resp = requests.get(url=subtitle_url)
        resp_json = json.loads(resp.text)
        body_list = resp_json.get('body')
        for body in body_list:
            result.append('{}-{}'.format(format_duration(body.get('from')), body.get('content')))
        return result
    except Exception as e:
        print(e)


def get_prompt_list(id, p=0):
    prompt = '请先用一句简短的话总结视频内容，然后再将视频字幕文本进行总结（如果有错别字请改正），在每句话的前面加上时间戳，每句话开头只需要一个开始时间。请注意不要超过5条，确保所有的句子都足够精简和清晰完整。\n'
    string = prompt
    result = []
    subtitle_list = get_subtitle_list(id, p)
    subtitle_url = get_subtitle_url(subtitle_list)
    content_list = get_subtitle_content(subtitle_url)
    for content in content_list:
        if len(string + content) > 4000:
            result.append(string)
            string = prompt
        string += '{}\n'.format(content)
    result.append(string)
    return result


def get_chatgpt(prompt, id):
    url = 'https://api.binjie.fun/api/generateStream'
    data = {
        'prompt': prompt,
        'userId': '#/chat/{}'.format(id),
        'network': False,
        'system': '',
        'withoutContext': False,
        'stream': False
    }
    headers = {
        'origin': 'https://chat.jinshutuan.com',
        'referer': 'https://chat.jinshutuan.com/'
    }
    try:
        with requests.get(url=url, data=data, headers=headers, stream=True) as resp:
            for line in resp.iter_lines():
                if line:
                    print(id, line.decode('utf-8'))
                    yield '{}\n'.format(line.decode('utf-8'))
    except Exception as e:
        print(e)


def get_play_audio(id, cid):
    if id.startswith('av'):
        url = 'https://api.bilibili.com/x/player/playurl?qn=120&fnval=4048&avid={}&cid={}'.format(id[2:], cid)
    else:
        url = 'https://api.bilibili.com/x/player/playurl?qn=120&fnval=4048&bvid={}&cid={}'.format(id, cid)
    try:
        resp = requests.get(url=url, headers=headers)
        resp_json = json.loads(resp.text)
        return resp_json.get('data', {}).get('dash', {}).get('audio', [''])
    except Exception as e:
        print(e)


def get_audio_url(id, p):
    view_data = get_view_data(id)
    title = view_data.get('title')
    print(id, title)
    if p and p != 1:
        pages = view_data.get('pages')
        for page in pages:
            if p == page.get('page'):
                cid = page.get('cid')
                return get_play_audio(id, cid)[0]
    else:
        cid = view_data.get('cid')
        return get_play_audio(id, cid)[0]


def download_data(id, url):
    headers = {
        'referer': 'https://www.bilibili.com/',
        'user-agent': 'Mozilla/5.0 AppleWebKit/537.36'
    }
    try:
        resp = requests.get(url=url, headers=headers)
        if not os.path.exists(data_path):
            os.makedirs(data_path)
        with open(os.path.join(data_path, '{}.wav'.format(id)), 'wb') as f:
            f.write(resp.content)
    except Exception as e:
        print(e)


def get_audio_text(id, p=0):
    audio_url = get_audio_url(id, p)
    base_url = audio_url.get('base_url')
    download_data(id, base_url)


def stream(prompt_list):
    ts = int(time.time() * 1000)
    for prompt in prompt_list:
        print(prompt)
        for text in get_chatgpt(prompt, ts):
            yield text


def get_location(url):
    try:
        resp = requests.get(url=url, allow_redirects=False)
        return resp.headers['Location']
    except Exception as e:
        print(e)


@app.route('/api', methods=['POST'])
def api_post():
    id = ''
    p = 0
    data = request.get_json()
    url = data.get('url')
    for i in range(2):
        if 'b23.tv' in url:
            url = get_location(url)
    match1 = re.search(r'BV([\w]+)', url)
    match2 = re.search(r'av([\w]+)', url)
    if match1:
        id = match1.group(1)
    elif match2:
        id = match2.group(1)
    match3 = re.search(r'p=([\w]+)', url)
    if match3:
        p = int(match3.group(1))
    prompt_list = get_prompt_list(id, p)
    return Response(stream(prompt_list))


@app.route('/title', methods=['POST'])
def title_post():
    id = ''
    data = request.get_json()
    url = data.get('url')
    for i in range(2):
        if 'b23.tv' in url:
            url = get_location(url)
    match1 = re.search(r'BV([\w]+)', url)
    match2 = re.search(r'av([\w]+)', url)
    if match1:
        id = match1.group(1)
    elif match2:
        id = match2.group(1)
    view_data = get_view_data(id)
    title = view_data.get('title')
    return Response(title)


@app.route('/', methods=['GET'])
def index():
    return html


if __name__ == '__main__':
    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app)
    server.serve_forever()
