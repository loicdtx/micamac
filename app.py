#!/usr/bin/env python3
import time

from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

EXAMPLE_FC = {
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Point",
        "coordinates": [
          16.3092041015625,
          1.6037944300589855
        ]
      }
    },
    {
      "type": "Feature",
      "properties": {},
      "geometry": {
        "type": "Point",
        "coordinates": [
          16.4794921875,
          1.598303410509457
        ]
      }
    }
  ]
}

POLYGONS = []

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/')
def index():
    return render_template('index.html', fc=EXAMPLE_FC)


@app.route('/polygon', methods = ['POST'])
def post_polygon():
    content = request.get_json(silent=True)
    POLYGONS.append(content)
    shutdown_server()
    return jsonify('Bye')


if __name__ == '__main__':
    print('Visit the address written below to select a subset of images to process')
    app.run(debug=False)
    print(POLYGONS)
