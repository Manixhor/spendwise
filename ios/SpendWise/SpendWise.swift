import UIKit
import WebKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {}

enum SpendWiseAction: String {
    case dashboard = "com.manixhor.spendwise.dashboard"
    case quickAdd = "com.manixhor.spendwise.quick-add"
    case repeatExpense = "com.manixhor.spendwise.repeat-expense"

    static let host = "site--spendwise--m9lhjm5ftxzt.code.run"

    var url: URL {
        var address = URLComponents()
        address.scheme = "https"
        address.host = Self.host
        address.path = "/dashboard/"
        switch self {
        case .dashboard:
            break
        case .quickAdd:
            address.queryItems = [URLQueryItem(name: "quick_add", value: "1")]
        case .repeatExpense:
            address.queryItems = [URLQueryItem(name: "quick_add", value: "repeat")]
        }
        // All components above are fixed strings controlled by the app.
        return address.url!
    }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    private var browser: SpendWiseViewController?

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = scene as? UIWindowScene else { return }
        let browser = SpendWiseViewController()
        self.browser = browser
        let window = UIWindow(windowScene: windowScene)
        window.rootViewController = browser
        self.window = window
        window.makeKeyAndVisible()
        let action = connectionOptions.shortcutItem.flatMap { SpendWiseAction(rawValue: $0.type) }
        browser.open(action ?? .dashboard)
    }

    func windowScene(
        _ windowScene: UIWindowScene,
        performActionFor shortcutItem: UIApplicationShortcutItem,
        completionHandler: @escaping (Bool) -> Void
    ) {
        guard let action = SpendWiseAction(rawValue: shortcutItem.type), let browser else {
            completionHandler(false)
            return
        }
        browser.open(action)
        completionHandler(true)
    }
}

final class SpendWiseViewController: UIViewController, WKNavigationDelegate, WKUIDelegate {
    private let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
    private var requestedURL = SpendWiseAction.dashboard.url

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor)
        ])
    }

    func open(_ action: SpendWiseAction) {
        loadViewIfNeeded()
        requestedURL = action.url
        webView.load(URLRequest(url: requestedURL))
    }

    private func isSpendWise(_ url: URL) -> Bool {
        url.scheme == "https" && url.host == SpendWiseAction.host && (url.port == nil || url.port == 443)
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if isSpendWise(url) {
            decisionHandler(.allow)
            return
        }
        if navigationAction.navigationType == .linkActivated && url.scheme == "https" {
            UIApplication.shared.open(url)
        }
        decisionHandler(.cancel)
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if navigationAction.targetFrame == nil,
           let url = navigationAction.request.url,
           isSpendWise(url) {
            webView.load(navigationAction.request)
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        let failure = error as NSError
        guard failure.code != NSURLErrorCancelled, presentedViewController == nil else { return }
        let alert = UIAlertController(
            title: "Couldn't open SpendWise",
            message: "Check your connection and try again.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Retry", style: .default) { [weak self] _ in
            guard let self else { return }
            self.webView.load(URLRequest(url: self.requestedURL))
        })
        alert.addAction(UIAlertAction(title: "Dismiss", style: .cancel))
        present(alert, animated: true)
    }
}
