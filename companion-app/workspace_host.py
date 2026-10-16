"""Two isolated WebView2 controls in one native window; no bridge on remote pages."""
import html,json,os,pathlib,sys,time,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.runtime'))
from workspace_queue import DATA,host_build
BASE='http://127.0.0.1:18764'

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    import msvcrt
    guard=open(DATA/'workspace-host.lock','a+b');guard.seek(0);guard.write(b'0');guard.flush();guard.seek(0)
    acquired=False
    for attempt in range(30):
        try:msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1);acquired=True;break
        except OSError:time.sleep(.3)
    if not acquired:return
    (DATA/'workspace-restart.request').unlink(missing_ok=True)
    loaded_build=host_build()
    import webview
    from local_features import browser_url
    webview.settings.update(ALLOW_FILE_URLS=False,ALLOW_DOWNLOADS=False,IGNORE_SSL_ERRORS=False,OPEN_EXTERNAL_LINKS_IN_BROWSER=False)
    window=webview.create_window('软糯小祥',BASE+'/?ui=workspace030',width=1240,height=820,min_size=(740,520),background_color='#F4F8FD',text_select=True,zoomable=True)
    def configure():
        import clr
        clr.AddReference('System.Windows.Forms');clr.AddReference('System.Drawing')
        from System import Uri
        from System.Drawing import Color,Icon,Font
        from System.Drawing.Text import PrivateFontCollection
        from System.Windows.Forms import SplitContainer,Orientation,DockStyle,ToolStrip,ToolStripButton,ToolStripTextBox,ToolStripGripStyle,Padding,BorderStyle,Keys,Timer,OpenFileDialog,DialogResult
        from Microsoft.Web.WebView2.WinForms import WebView2,CoreWebView2CreationProperties
        from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState
        fonts=PrivateFontCollection();fonts.AddFontFile(str(ROOT/'web/fonts/ZCOOLKuaiLe-Regular.ttf'));rounded=Font(fonts.Families[0],11.0)
        form=window.native;form.Font=rounded;form.Icon=Icon(str(ROOT/'assets'/'xy-sakiko-pixel.ico'));left=form.webview
        split=SplitContainer();split.Dock=DockStyle.Fill;split.Orientation=Orientation.Vertical
        form.Controls.Remove(left);form.Controls.Add(split);split.Panel1.Controls.Add(left);left.Dock=DockStyle.Fill
        def trusted_navigation(sender,e):
            if not str(e.Uri).startswith(BASE+'/'):e.Cancel=True
        left.NavigationStarting+=trusted_navigation
        split.Panel1MinSize=340;split.Panel2MinSize=300;split.Panel2Collapsed=True;split.SplitterWidth=5
        right=WebView2();props=CoreWebView2CreationProperties();props.UserDataFolder=str(DATA/'workspace-remote-profile');right.CreationProperties=props;right.Dock=DockStyle.Fill
        split.Panel2.Controls.Add(right)
        bar=ToolStrip();bar.Dock=DockStyle.Top;bar.BackColor=Color.FromArgb(239,245,253);bar.ForeColor=Color.FromArgb(64,85,114);bar.Font=rounded;bar.GripStyle=ToolStripGripStyle.Hidden;bar.AutoSize=False;bar.Height=48;bar.Padding=Padding(9,7,9,7)
        address=ToolStripTextBox();address.Font=rounded;address.BorderStyle=getattr(BorderStyle,'None');address.BackColor=Color.White;address.AutoSize=False;address.Width=300
        current={'id':None,'pending':None,'file':None}
        def report(state,detail):
            if not current['id']:return
            folder=DATA/'native-status';folder.mkdir(exist_ok=True)
            target=folder/(current['id']+'.json');temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps({'id':current['id'],'status':state,'detail':detail,'engine':'WebView2','layout':'same_window_split'},ensure_ascii=False),encoding='utf-8');temp.replace(target)
        def expand():
            split.Panel2Collapsed=False;split.SplitterDistance=max(340,int(form.ClientSize.Width*.43));right.BringToFront();bar.BringToFront()
        def navigate(url):
            current['file']=None;expand()
            if right.CoreWebView2 is None:current['pending']=url
            else:right.CoreWebView2.Navigate(url)
        def close(*_):split.Panel2Collapsed=True;report('closed','右侧工作区已收起。')
        def from_address(*_):
            try:navigate(browser_url(str(address.Text)))
            except ValueError:address.Text='请输入公开HTTP/HTTPS网址'
        for label,fn in [('←',lambda *_:right.GoBack() if right.CanGoBack else None),('→',lambda *_:right.GoForward() if right.CanGoForward else None),('↻',lambda *_:right.Reload()),('收起',close)]:
            button=ToolStripButton(label);button.Click+=fn;bar.Items.Add(button)
        bar.Items.Add(address);go=ToolStripButton('前往');go.Click+=from_address;bar.Items.Add(go)
        def key(sender,e):
            if e.KeyCode==Keys.Enter:from_address();e.SuppressKeyPress=True
        address.KeyDown+=key;split.Panel2.Controls.Add(bar);bar.BringToFront()
        def resized(*_):address.Width=max(100,split.Panel2.ClientSize.Width-230)
        split.SplitterMoved+=resized;form.Resize+=resized
        def ready(sender,event):
            if not event.IsSuccess:report('failed','右侧WebView2初始化失败。');return
            core=right.CoreWebView2;core.Settings.AreDevToolsEnabled=False;core.Settings.AreHostObjectsAllowed=False;core.Settings.IsWebMessageEnabled=False
            def permission(sender,e):e.State=CoreWebView2PermissionState.Deny
            core.PermissionRequested+=permission
            def download(sender,e):e.Cancel=True
            core.DownloadStarting+=download
            def starting(sender,e):
                url=str(e.Uri)
                if url.startswith(BASE+'/workspace/map'):return
                if current['file'] and url==current['file']:return
                if url=='about:blank':return
                try:browser_url(url)
                except ValueError:e.Cancel=True;report('failed','已阻止非公开网页或未选择的本机文件。')
            core.NavigationStarting+=starting
            def completed(sender,e):
                address.Text=str(core.Source);report('loaded' if e.IsSuccess else 'failed','已在同一窗口右侧载入。' if e.IsSuccess else '右侧页面加载失败，请重试。')
            core.NavigationCompleted+=completed
            def popup(sender,e):
                e.Handled=True
                try:navigate(browser_url(str(e.Uri)))
                except ValueError:pass
            core.NewWindowRequested+=popup
            if current['pending']:core.Navigate(current.pop('pending'))
        right.CoreWebView2InitializationCompleted+=ready;right.EnsureCoreWebView2Async(None)
        def select_file():
            picker=OpenFileDialog();picker.Filter='可预览文件|*.pdf;*.png;*.jpg;*.jpeg;*.webp;*.txt;*.md;*.json;*.docx';picker.Multiselect=False
            if picker.ShowDialog(form)!=DialogResult.OK:return
            path=pathlib.Path(str(picker.FileName));expand()
            if path.suffix.lower() in ('.pdf','.png','.jpg','.jpeg','.webp'):
                current['file']=path.as_uri();right.CoreWebView2.Navigate(current['file'])
            else:
                if path.stat().st_size>4000000:report('failed','文本预览限4MB。');return
                if path.suffix.lower()=='.docx':
                    import zipfile,xml.etree.ElementTree as ET
                    with zipfile.ZipFile(path) as z:
                        info=z.getinfo('word/document.xml')
                        if info.file_size>8000000:report('failed','文档文字部分过大。');return
                        root=ET.fromstring(z.read(info));text='\n'.join(''.join(p.itertext()) for p in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
                else:text=path.read_text(encoding='utf-8',errors='replace')
                right.CoreWebView2.NavigateToString('<meta charset=utf-8><style>body{background:#f7faff;padding:24px;font:16px/1.7 sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h3>'+html.escape(path.name)+'</h3><pre>'+html.escape(text)+'</pre>')
        def tick(*_):
            if (DATA/'workspace-restart.request').exists():
                timer.Stop();form.Close();return
            heartbeat=DATA/'workspace-heartbeat.json';heartbeat.write_text(json.dumps({'time':time.time(),'pid':os.getpid(),'host_build':loaded_build,'layout':'same_window_split','panels':2,'right_visible':not split.Panel2Collapsed,'left_width':split.Panel1.Width,'right_width':split.Panel2.Width}),encoding='utf-8')
            folder=DATA/'workspace-queue'
            for file in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime) if folder.exists() else []:
                try:
                    job=json.loads(file.read_text(encoding='utf-8'));file.unlink()
                    if time.time()-job.get('created_at',0)>120:continue
                    current['id']=job['id'];kind=job['kind']
                    if kind=='focus':
                        if form.WindowState.ToString()=='Minimized':
                            from System.Windows.Forms import FormWindowState
                            form.WindowState=FormWindowState.Normal
                        form.Activate()
                    elif kind=='browser':navigate(browser_url(job['url']))
                    elif kind=='map':navigate(BASE+'/workspace/map?'+urllib.parse.urlencode({'query':job.get('query','')}))
                    elif kind=='file_picker':select_file()
                    elif kind=='close':close()
                except Exception as exc:report('failed','工作区处理失败：'+type(exc).__name__)
        timer=Timer();timer.Interval=700;timer.Tick+=tick;timer.Start()
        window._workspace_refs=(split,right,bar,timer,guard,fonts,rounded)
    window.events.before_show+=configure
    try:webview.start(gui='edgechromium',private_mode=False,storage_path=str(DATA/'workspace-app-profile'),debug=False)
    except Exception as exc:
        (DATA/'workspace-error.txt').write_text('启动失败：'+type(exc).__name__,encoding='utf-8')
    finally:
        try:(DATA/'workspace-heartbeat.json').unlink(missing_ok=True)
        except OSError:pass

if __name__=='__main__':main()
