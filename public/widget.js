/**
 * ИИ-кассир — виджет встраивания чата в личный кабинет партнёра.
 *
 * Использование:
 *   <script src="https://iikassa.ru/widget.js"></script>
 *   <script>
 *     AiCashier.init({
 *       token: 'ECOMKASSA_API_TOKEN',  // токен, полученный через ваш вход по логину/паролю кассы
 *       shopId: 'STORE_ID',           // рекомендуется: передайте storeId магазина по умолчанию
 *                                      // из вашего ЛК — тогда чат сразу будет слать чеки в
 *                                      // нужный магазин, без авто-выбора или вопроса пользователю
 *       button: true,                 // true — показать плавающую кнопку; false — вызывать AiCashier.open() вручную
 *
 *       // Внешний вид окна (все необязательны, есть разумные значения по умолчанию):
 *       width: 440,                   // ширина попапа на десктопе, px
 *       height: 680,                  // высота попапа на десктопе, px
 *       mobileBreakpoint: 640,        // ниже этой ширины экрана — окно раскрывается на весь экран
 *       fullscreenOnMobile: true,     // false — не раскрывать на весь экран, всегда показывать маленькое окно
 *       fullscreen: false             // true — всегда на весь экран, даже на десктопе
 *     });
 *   </script>
 *
 * Токен ecomkassa_token — это обычный API-токен Ecomkassa (тот же, что использует
 * мобильное приложение), полученный один раз через логин/пароль. Секретных ключей
 * партнёра здесь не требуется — сервер сам проверяет токен и открывает чат только
 * для его настоящего владельца.
 *
 * Магазин (group_code) определяется так: если передан shopId — используется именно он
 * (и всегда имеет приоритет, даже если раньше уже был выбран другой магазин — так что
 * можно передавать актуальный "магазин по умолчанию" из вашего ЛК при каждом открытии);
 * если shopId не передан и у пользователя один магазин — подставится сам; если магазинов
 * несколько и shopId не передан — пользователь один раз выберет его в самом чате.
 *
 * По умолчанию на мобильных экранах (уже mobileBreakpoint) окно само раскрывается
 * на весь экран — так удобнее печатать и читать чат на телефоне. На десктопе
 * остаётся компактный попап. Поведение можно переопределить через опции выше.
 */
(function (window, document) {
  'use strict';

  var BASE_URL = 'https://iikassa.ru';
  var PARTNER_EMBED_URL = 'https://functions.poehali.dev/10219b97-9c66-4c02-b8a3-939f2d6e06c6';

  var state = {
    options: null,
    overlay: null,
    panel: null,
    iframe: null,
    button: null,
    resizeHandler: null
  };

  function log(message) {
    if (window.console && console.warn) {
      console.warn('[AiCashier] ' + message);
    }
  }

  function isFullscreenMode(opts) {
    if (opts.fullscreen) return true;
    if (opts.fullscreenOnMobile === false) return false;
    var breakpoint = opts.mobileBreakpoint || 640;
    return window.innerWidth <= breakpoint;
  }

  function applyPanelStyle(opts) {
    var fullscreen = isFullscreenMode(opts);
    var width = opts.width || 440;
    var height = opts.height || 680;

    if (fullscreen) {
      state.overlay.style.padding = '0';
      state.overlay.style.background = '#0f0f14';
      state.panel.style.cssText = [
        'position:relative', 'width:100%', 'height:100%',
        'max-width:none', 'max-height:none',
        'background:#0f0f14', 'border-radius:0',
        'overflow:hidden'
      ].join(';');
    } else {
      state.overlay.style.padding = '16px';
      state.overlay.style.background = 'rgba(15,15,20,0.55)';
      state.panel.style.cssText = [
        'position:relative', 'width:100%', 'max-width:' + width + 'px',
        'height:' + height + 'px', 'max-height:92vh',
        'background:#0f0f14', 'border-radius:16px',
        'overflow:hidden', 'box-shadow:0 20px 60px rgba(0,0,0,0.4)'
      ].join(';');
    }
  }

  function createOverlay(opts) {
    var overlay = document.createElement('div');
    overlay.setAttribute('data-ai-cashier-overlay', '');
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:2147483000',
      'display:flex', 'align-items:center', 'justify-content:center',
      'box-sizing:border-box'
    ].join(';');

    var panel = document.createElement('div');
    panel.style.boxSizing = 'border-box';

    var closeBtn = document.createElement('button');
    closeBtn.setAttribute('aria-label', 'Закрыть');
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText = [
      'position:absolute', 'top:calc(8px + env(safe-area-inset-top, 0px))', 'right:8px', 'z-index:2',
      'width:32px', 'height:32px', 'border-radius:8px', 'border:0',
      'background:rgba(255,255,255,0.08)', 'color:#fff', 'font-size:20px',
      'line-height:1', 'cursor:pointer'
    ].join(';');
    closeBtn.onclick = close;

    var iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%;height:100%;border:0;display:block;';
    iframe.setAttribute('title', 'ИИ-кассир');

    panel.appendChild(closeBtn);
    panel.appendChild(iframe);
    overlay.appendChild(panel);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });

    state.overlay = overlay;
    state.panel = panel;
    state.iframe = iframe;

    applyPanelStyle(opts);

    state.resizeHandler = function () {
      applyPanelStyle(opts);
    };
    window.addEventListener('resize', state.resizeHandler);

    return overlay;
  }

  function close() {
    if (state.resizeHandler) {
      window.removeEventListener('resize', state.resizeHandler);
      state.resizeHandler = null;
    }
    if (state.overlay && state.overlay.parentNode) {
      state.overlay.parentNode.removeChild(state.overlay);
    }
    if (state.iframe) {
      state.iframe.src = 'about:blank';
    }
    state.overlay = null;
    state.panel = null;
    state.iframe = null;
  }

  function open(options) {
    var opts = options || state.options;
    if (!opts || !opts.token) {
      log('Не передан token — вызовите AiCashier.open({ token: "..." })');
      return Promise.reject(new Error('token is required'));
    }

    return fetch(PARTNER_EMBED_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'issue_from_token',
        ecomkassa_token: opts.token,
        partner_id: opts.partnerId || 'widget',
        shop_id: opts.shopId || ''
      })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || 'Не удалось открыть ИИ-кассира');
          return data;
        });
      })
      .then(function (data) {
        var overlay = createOverlay(opts);
        document.body.appendChild(overlay);
        state.iframe.src = BASE_URL + data.embed_path;
      })
      .catch(function (err) {
        log(err.message || String(err));
        if (typeof opts.onError === 'function') opts.onError(err);
      });
  }

  function createFloatingButton(opts) {
    if (state.button) return;

    var btn = document.createElement('button');
    btn.setAttribute('aria-label', 'Открыть ИИ-кассира');
    btn.innerHTML = '&#128172;';
    btn.style.cssText = [
      'position:fixed', 'right:20px', 'bottom:20px', 'z-index:2147482999',
      'width:56px', 'height:56px', 'border-radius:50%', 'border:0',
      'background:#7c3aed', 'color:#fff', 'font-size:24px', 'cursor:pointer',
      'box-shadow:0 8px 24px rgba(124,58,237,0.4)'
    ].join(';');
    btn.onclick = function () {
      open(opts);
    };

    document.body.appendChild(btn);
    state.button = btn;
  }

  function init(options) {
    if (!options || !options.token) {
      log('AiCashier.init требует { token: "..." }');
      return;
    }
    state.options = options;

    if (options.button !== false) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
          createFloatingButton(options);
        });
      } else {
        createFloatingButton(options);
      }
    }
  }

  window.AiCashier = {
    init: init,
    open: open,
    close: close
  };
})(window, document);