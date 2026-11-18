### Executor API (contract v1; master-owned). Provided by `review` (the files `dunzo/api.js`, `dunzo/card.js`), used by executors such as `starters`.
An executor is a directory of static web files with `index.html` at its top, run in `<iframe sandbox="allow-scripts">` (no `allow-same-origin`). It loads the app's two generated files by relative URL: `<script src="dunzo/api.js"></script><script src="dunzo/card.js"></script>`. Its own files are loaded by relative path; nothing else on the server is reachable (strict CSP: scripts/styles/images/audio/video/fonts from the server only, inline allowed, no network, no eval, no navigation).
```js
window.dunzoCard = { note: { id, properties, media: [ {id, mime, size, url} ] }, index, card_count }   // from dunzo/card.js
dunzo.card                      // same object as window.dunzoCard
dunzo.onInit(callback)          // callback(card) once the page has loaded (immediately if it already has)
dunzo.done(grade, detail?)      // grade: integer 1..4 (1 Again, 2 Hard, 3 Good, 4 Easy); detail: optional JSON-serializable value stored with the review
dunzo.mediaUrl(hash)            // URL for a media hash listed in card.note.media, else null
```
Messages to the host (the only channel; `parent.postMessage(msg, "*")`): `{type:"done", grade, detail?}` and `{type:"error", message}` (reported for a missing card.js or a throwing onInit callback). The host accepts messages only when `event.source` is its own iframe window, validates `grade`, and moves on to the next card after recording a `done`. The host never shows grade buttons; the executor decides whether to show its own. An executor may send `done` at any time. There is no host-to-executor message.
