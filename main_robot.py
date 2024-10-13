import websocket
import json
import threading
import sounddevice as sd
import numpy as np
import base64
import time

# APIキーをファイルから読み込む関数
def load_api_key(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except Exception as e:
        print(f"APIキーの読み込み中にエラーが発生しました: {e}")
        return None

# グローバル変数の初期化
audio_output_data = b''
audio_lock = threading.Lock()
is_running = True  # フラグを追加して、ループを制御
last_message_time = time.time()  # 最後のメッセージのタイムスタンプ
timeout_seconds = 300  # 5分（300秒）でタイムアウト

# ロボットの動作を定義
def move_forward():
    print("ロボットが前進します。")
    # 実際のロボット制御コードをここに追加

def move_backward():
    print("ロボットが後退します。")
    # 実際のロボット制御コードをここに追加

def take_picture():
    print("ロボットが写真を撮影します。")
    # 実際のロボット制御コードをここに追加

def execute_function(function_name, arguments):
    if function_name == 'move_forward':
        move_forward()
    elif function_name == 'move_backward':
        move_backward()
    elif function_name == 'take_picture':
        take_picture()
    else:
        print(f"未知の関数が呼び出されました: {function_name}")

def send_function_call_output(ws, item_id, function_name, arguments):
    event = {
        'type': 'conversation.item.create',
        'item': {
            'type': 'function_call_output',
            'status': 'completed',
            'input_item_id': item_id,
            'content': [{
                'type': 'json',
                'data': {"result": "success"}
            }]
        }
    }
    ws.send(json.dumps(event))
    # 新しいレスポンスをリクエスト
    ws.send(json.dumps({'type': 'response.create'}))

def on_message(ws, message):
    global audio_output_data  # global宣言を追加
    event = json.loads(message)
    #print("受信したイベント:", event)
    # print(event['item']['type'])

    if event['type'] == 'conversation.item.created':

        item = event['item']
        if item['type'] == 'function_call':
            print('Function_call:')
            print(event)
            function_call = item['content'][0]
            function_name = function_call['name']
            arguments = function_call.get('arguments', {})
            # 関数を実行
            execute_function(function_name, arguments)
            # 関数呼び出しの出力を送信
            send_function_call_output(ws, item['id'], function_name, arguments)

            
    elif event['type'] == 'response.audio.delta':
        #print('Audio 受信:')
        #print(event)
        # 受信した音声データを追加
        try:
            audio_chunk_base64 = event['content']['audio']
        except:
            audio_chunk_base64 = event['delta']
        audio_chunk = base64.b64decode(audio_chunk_base64)
        audio_output_data += audio_chunk  # グローバル変数に追加
    elif event['type'] == 'response.audio.done':
        print('Audio　受信完了')
        # 音声データの受信が完了したら再生
        play_audio_data(audio_output_data)
        audio_output_data = b''  # バッファをクリア
    # 音声データが含まれるイベントが受信されたとき
    elif event['type'] == 'response.output_item.done':
        for content_item in event['item']['content']:
            #print('response.output_item.done')
            #print(event)
            if content_item['type'] == 'audio':
                # 音声データが含まれている場合、その音声を再生
                transcript = content_item.get('transcript', '')
                print(f"音声の内容: {transcript}")
                play_audio_data(content_item['audio'])  # 音声データを再生する関数

    elif event['type'] == 'error':
        print("エラーが発生しました:", event['error'])
    else:
        print(event)

def on_error(ws, error):
    print("WebSocketエラー:", error)

def on_close(ws, close_status_code, close_msg):
    global is_running  # フラグを変更してループを終了
    print(f"WebSocket接続が閉じられました。コード: {close_status_code}, メッセージ: {close_msg}")
    is_running = False  # WebSocketが閉じたらフラグをFalseに

def on_open(ws):
    print("WebSocket接続が確立されました。")

    # セッションを更新して関数を設定
    event = {
        'type': 'session.update',
        'session': {
            'modalities': ['audio', 'text'],
            'instructions': '''あなたはロボットAIです。
                  日本語で応答してください。会話はすべて日本語で行われます。
                  ロボットとして、会話を行い、指示された動作を実施します。
                  前進、後退、写真を撮ることが出来ます。''',
            "output_audio_format": "pcm16",
            "voice": "alloy",
            # 'default_response': {
            #     'language': 'ja',  # 日本語（ja）を指定
            #     #'modalities': ['audio']  # 音声応答を指定
            # },
            }
    }
    function_event = {
        'type': 'session.update',
        'session':{
            'tools': [
                {
                    'type':'function',
                    'name': 'move_forward',
                    'description': '前進します。',
                    'parameters': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    }
                },
                {
                    'type':'function',
                    'name': 'move_backward',
                    'description': '後退します。',
                    'parameters': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    }
                },
                {
                    'type':'function',
                    'name': 'take_picture',
                    'description': '写真を撮影します',
                    'parameters': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    }
                }
            ],
            "tool_choice": "auto",
            "temperature": 0.8
        }
    }
    ws.send(json.dumps(event))
    ws.send(json.dumps(function_event))

    # 音声入力を開始
    threading.Thread(target=record_audio, args=(ws,)).start()

def record_audio(ws):
    fs = 24000  # サンプルレート
    #fs = 44100  # サンプルレート
    # device_info = sd.query_devices(1)
    # print(device_info)
    channels = 1
    dtype = 'int16'

    def callback(indata, frames, time, status):
        if status:
            print(status)
        if not is_running:
            return  # WebSocketが閉じたら音声入力を終了

        # 音声データをbytesに変換
        pcm_data = indata.tobytes()

        # base64でエンコード
        pcm_base64 = base64.b64encode(pcm_data).decode('utf-8')
        #print(f"エンコードされた音声データの一部: {pcm_base64[:50]}...")  # デバッグのために最初の50文字を表示

        # audioパラメータとして送信
        event = {
            "type": "input_audio_buffer.append",
            "audio": pcm_base64  # 'audio' パラメータにエンコード済みの音声データを追加

        }

        try:
            # WebSocketで送信
            ws.send(json.dumps(event))
        except Exception as e:
            print(f"送信中にエラーが発生しました: {e}")

    #with sd.InputStream(samplerate=fs, channels=channels, dtype=dtype, callback=callback):
    with sd.InputStream(device=1,samplerate=fs, channels=channels, dtype=dtype, callback=callback):
        print("音声入力を開始します。終了するにはCtrl+Cを押してください。")
        try:
            while is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

def play_audio_data(audio_data):
    fs = 24000  # サンプルレート
    #fs = 44100 
    channels = 1
    dtype = 'int16'

    # バイトデータをnumpy配列に変換
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    sd.play(audio_array, samplerate=fs)
    sd.wait()

def check_timeout(ws):
    global last_message_time
    while is_running:
        if time.time() - last_message_time > timeout_seconds:
            print(f"{timeout_seconds/60}分間応答がなかったため、接続を終了します。")
            ws.close()
            break
        time.sleep(5)  # 5秒ごとにチェック

if __name__ == "__main__":
    # APIキーをファイルから読み込む
    api_key = load_api_key('api_key.txt')

    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        header={
            "Authorization": 'Bearer ' + api_key,
            "OpenAI-Beta": "realtime=v1"
        },
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )

    # WebSocketを別スレッドで実行
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    # タイムアウトチェックを別スレッドで実行
    timeout_thread = threading.Thread(target=check_timeout, args=(ws,))
    timeout_thread.daemon = True
    timeout_thread.start()

    try:
        while is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        ws.close()