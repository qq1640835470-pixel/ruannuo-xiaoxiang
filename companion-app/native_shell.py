"""An isolated WebView2 browser window: no js_api, no automation bridge to remote pages."""
from __future__ import annotations
import app_paths
import argparse,json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.runtime'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--browser-id',required=True);args=parser.parse_args()
    ident=args.browser_id
    if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Invalid browser id')
    data=app_paths.DATA
    status=data/'native-status'/(ident+'.json');status.parent.mkdir(parents=True,exist_ok=True)
    def report(state,detail):
        out={'id':ident,'status':state,'detail':detail,'engine':'WebView2'}
        tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8');tmp.replace(status)
    try:
        import webview
        from local_features import browser_url
        url=browser_url(os.environ.pop('XY_BROWSER_START_URL','https://www.bilibili.com/'))
        webview.settings.update(ALLOW_FILE_URLS=False,ALLOW_DOWNLOADS=False,IGNORE_SSL_ERRORS=False,OPEN_EXTERNAL_LINKS_IN_BROWSER=False)
        window=webview.create_window('小祥浏览器 · WebView2',url=url,width=1060,height=760,min_size=(540,420),background_color='#F4F8FD',text_select=True,zoomable=True)
        def configure():
            import clr
            clr.AddReference('System.Windows.Forms');clr.AddReference('System.Drawing')
            from System import Action,Uri
            from System.Windows.Forms import ToolStrip,ToolStripButton,ToolStripTextBox,DockStyle,Keys
            from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState
            def setup():
                form=window.native;view=form.webview
                strip=ToolStrip();strip.Dock=DockStyle.Top;strip.AutoSize=True
                address=ToolStripTextBox();address.AutoSize=False;address.Width=max(240,form.ClientSize.Width-210);address.Text=url
                def navigate(*_):
                    try:view.CoreWebView2.Navigate(browser_url(str(address.Text)))
                    except Exception:address.Text='请输入公开网站的HTTP/HTTPS地址'
                for label,fn in [('←',lambda *_:view.CoreWebView2.GoBack() if view.CoreWebView2.CanGoBack else None),('→',lambda *_:view.CoreWebView2.GoForward() if view.CoreWebView2.CanGoForward else None),('↻',lambda *_:view.CoreWebView2.Reload())]:
                    b=ToolStripButton(label);b.Click+=fn;strip.Items.Add(b)
                strip.Items.Add(address);go=ToolStripButton('前往');go.Click+=navigate;strip.Items.Add(go)
                def key(sender,e):
                    if e.KeyCode==Keys.Enter:navigate();e.SuppressKeyPress=True
                address.KeyDown+=key
                form.Controls.Add(strip);strip.BringToFront();form.Controls.SetChildIndex(strip,0)
                def resized(*_):address.Width=max(220,form.ClientSize.Width-210)
                form.Resize+=resized
                def ready(*_):
                    core=view.CoreWebView2
                    def permission(sender,e):e.State=CoreWebView2PermissionState.Deny
                    core.PermissionRequested+=permission
                    def navigating(sender,e):
                        try:browser_url(str(e.Uri))
                        except ValueError:e.Cancel=True
                    core.NavigationStarting+=navigating
                    def completed(sender,e):
                        address.Text=str(core.Source)
                        report('loaded' if e.IsSuccess else 'failed','页面已加载。' if e.IsSuccess else '页面未加载成功，请检查网址或网络。')
                    core.NavigationCompleted+=completed
                    report('ready','WebView2内核已初始化；等待页面加载。')
                if view.CoreWebView2 is not None:ready()
                else:view.CoreWebView2InitializationCompleted+=ready
            setup()
        window.events.before_show+=configure
        window.events.closed+=lambda:report('closed','浏览器窗口已关闭。')
        report('starting','正在初始化WebView2内核。')
        webview.start(gui='edgechromium',private_mode=True,debug=False)
    except Exception as exc:
        report('failed','浏览器启动失败：'+type(exc).__name__+'；可在运行诊断中检查组件。')

if __name__=='__main__':main()
