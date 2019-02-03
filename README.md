# my365 : Image Downloader
2019年2月28日にサービスが終了するSNS「my365」に投稿した写真を一括で取得するためのツールです。
公式の手順書に従うと手作業で１枚１枚ダウンロードすることになるのですが、長期間利用していると写真の枚数が2000枚以上にもなり、手作業でのダウンロードは非現実的ですので、自動化しました。

## Dependency (依存)
- 使用言語
  - python
- 利用ライブラリ
  - certifi==2018.4.16
  - chardet==3.0.4
  - idna==2.7
  - numpy==1.14.5
  - pandas==0.23.1
  - python-dateutil==2.7.3
  - pytz==2018.4
  - requests>=2.20.0
  - six==1.11.0
  - urllib3==1.23
- 利用ライブラリのインストール 
```
pip install -r requirements.txt
```

## Usage (使い方)
1. ローカル環境へダウンロードする。gitでやる場合は下記のコマンド。zipダウンロードでも良い。
```
git clone https://github.com/cotton928/download-my365-images.git
```

2. configファイル（config.ini）にアカウント情報を設定する。具体的には下記の部分
```
[user]
# ユーザアカウント
account = アカウントIDをここに設定
# パスワード
password = パスワードをここに設定
```

3. ツールを起動する
```
python my365.py
```

## Process (動作仕様)
1. my365へログインする
2. 当月から最古月（デフォルトでは2011年12月）まで以下の処理をループする
    1. 月間カレンダーから投稿がある日を確認し、個別ページのURLを抽出する
    2. 個別ページへアクセスし、投稿画像（600x600）のURLを抽出する
3. 抽出したURLにアクセスし、投稿画像をダウンロードする


## Licence (ライセンス)
This software is released under the MIT License, see LICENSE.

## Note (注意点)
- 一応動作することは確認していますが、使い捨てのツールなのでバグ潰しはあまりやっていません。バグを見つけたらご連絡ください。
