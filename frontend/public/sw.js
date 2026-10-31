// 1. 强制等待中的 Service Worker 立即激活，并接管当前打开的页面
self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(clients.claim());
});

// 2. 增加 fetch 事件监听器（满足 Android Chrome 的 PWA 安装条件）
self.addEventListener('fetch', function (event) {
  // 保持为空即可。不拦截请求，纯作为 PWA 安装的条件。
});

// 3. 监听后端发来的推送事件 (Web Push)
self.addEventListener('push', function (event) {
  let data = {};

  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      console.error('推送数据解析失败，尝试作为纯文本处理', e);
      data = { body: event.data.text() };
    }
  }

  const title = data.title || '新消息通知';
  const options = {
    body: data.body || '您有一条未读消息',
    icon: '/favicon.svg',
    data: { url: data.url || '/' }, // 保存后端指定的跳转链接
    vibrate: [200, 100, 200]
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// 4. 监听通知点击事件（兼容：后端推送 和 前端本地弹窗）
self.addEventListener('notificationclick', function (event) {
  // 点击后立刻关闭通知
  event.notification.close();

  // 获取我们在弹窗时塞入的数据（无论是后端传的还是前端传的）
  const notificationData = event.notification.data || {};
  const targetUrl = notificationData.url || '/';
  const notificationId = notificationData.notificationId; // 前端弹窗时传过来的 ID

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windowClients) {
      // 1. 尝试寻找已经打开的项目窗口
      for (let i = 0; i < windowClients.length; i++) {
        let client = windowClients[i];

        // 只要页面属于你的域名，就聚焦它
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          // 👇 核心：如果是前端本地触发的弹窗，发消息给前端，通知它执行 onClick 业务逻辑
          if (notificationId) {
            client.postMessage({
              type: 'NOTIFICATION_CLICKED',
              notificationId: notificationId
            });
          }

          // 聚焦窗口
          return client.focus();
        }
      }

      // 2. 如果没有找到已打开的页面，则开启一个新窗口
      if (clients.openWindow) {
        const urlToOpen = targetUrl.startsWith('http') ? targetUrl : (self.location.origin + targetUrl);
        return clients.openWindow(urlToOpen);
      }
    })
  );
});