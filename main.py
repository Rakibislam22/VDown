
# kivy_video_downloader.py
import os
import threading
import traceback

from kivy.core.window import Window

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import (
    StringProperty,
    NumericProperty,
    BooleanProperty,
    ListProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner

from kivy.utils import escape_markup
import webbrowser

import yt_dlp

KV = '''
<MainUI>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(12)

    BoxLayout:
        size_hint_y: None
        height: dp(40)
        TextInput:
            id: url_input
            hint_text: 'Paste video URL here (YouTube, Vimeo, etc.)'
            multiline: False
            on_text_validate: root.fetch_qualities()
        Button:
            text: 'Fetch Qualities'
            size_hint_x: None
            width: dp(140)
            on_release: root.fetch_qualities()

    Spinner:
        id: quality_spinner
        text: 'Select quality'
        values: root.quality_list
        size_hint_y: None
        height: dp(40)

    BoxLayout:
        size_hint_y: None
        height: dp(40)
        Label:
            text: 'Save to:'
            size_hint_x: None
            width: dp(80)
        TextInput:
            id: path_input
            text: root.save_path
            multiline: False
        Button:
            text: 'Browse'
            size_hint_x: None
            width: dp(100)
            on_release: root.open_dir_chooser()

    Button:
        text: 'Download'
        size_hint_y: None
        height: dp(40)
        on_release: root.on_download_button()

    ProgressBar:
        id: bar
        max: 1
        value: root.progress
        size_hint_y: None
        height: dp(20)

    Label:
        id: status_label
        text: root.status
        size_hint_y: None
        height: dp(30)

    ScrollView:
        do_scroll_x: False
        Label:
            id: log_label
            text_size: self.width, None
            size_hint_y: None
            height: self.texture_size[1]
            text: root.log_text
            markup: True
               
    Label:
        text: "[ref=https://rakibislam22.github.io/pro]© 2025 Rakib Islam[/ref]"
        markup: True
        size_hint_y: None
        height: 30
        on_ref_press: import webbrowser; webbrowser.open(args[1])
'''

def get_default_download_path():
    home = os.path.expanduser('~')
    path = os.path.join(home, 'Downloads')
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = os.getcwd()
    return path

class MainUI(BoxLayout):
    status = StringProperty('Ready')
    log_text = StringProperty('')
    progress = NumericProperty(0.0)
    save_path = StringProperty(get_default_download_path())
    downloading = BooleanProperty(False)
    quality_list = ListProperty([])
    selected_format_id = StringProperty('')

    def append_log(self, msg):
        # Prepend newest at top
        self.log_text = f"{msg}\n" + self.log_text

    def open_dir_chooser(self):
        chooser = FileChooserIconView(path=self.save_path, dirselect=True)
        btn_layout = BoxLayout(size_hint_y=None, height='40dp')
        from kivy.uix.button import Button

        select_btn = Button(text='Select')
        cancel_btn = Button(text='Cancel')
        btn_layout.add_widget(select_btn)
        btn_layout.add_widget(cancel_btn)

        content = BoxLayout(orientation='vertical')
        content.add_widget(chooser)
        content.add_widget(btn_layout)

        popup = Popup(title='Select Download Folder', content=content, size_hint=(0.9, 0.9))

        def do_select(instance):
            sel = chooser.selection
            if sel:
                chosen = sel[0]
                if os.path.isfile(chosen):
                    chosen = os.path.dirname(chosen)
                self.save_path = chosen
                try:
                    self.ids.path_input.text = self.save_path
                except Exception:
                    pass
                self.append_log(f'Download directory changed to: {self.save_path}')
                popup.dismiss()

        def do_cancel(instance):
            popup.dismiss()

        select_btn.bind(on_release=do_select)
        cancel_btn.bind(on_release=do_cancel)
        popup.open()

    def fetch_qualities(self):
        url = self.ids.url_input.text.strip() if 'url_input' in self.ids else ''
        if not url:
            self.append_log('[color=ff3333]Please enter a URL[/color]')
            return
        self.append_log('Fetching available formats...')
        threading.Thread(target=self._fetch_qualities_thread, args=(url,), daemon=True).start()

    def _fetch_qualities_thread(self, url):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = []
            seen = set()
            for f in info.get('formats', []):
                if f.get('vcodec') and f.get('vcodec') != 'none':
                    fid = f.get('format_id') or str(f.get('tbr') or f.get('height') or f.get('width') or '')
                    note = f.get('format_note') or (f.get('height') and f"{f.get('height')}p") or ''
                    ext = f.get('ext') or ''
                    display_parts = [p for p in (fid, note, ext) if p]
                    display = " - ".join(display_parts)
                    if display not in seen:
                        seen.add(display)
                        formats.append(display)

            if not formats:
                Clock.schedule_once(lambda dt: self.append_log('[color=ff3333]No video formats found.[/color]'), 0)

            Clock.schedule_once(lambda dt: self._update_formats_in_ui(formats), 0)
            Clock.schedule_once(lambda dt: self.append_log('Available qualities fetched.'), 0)
        except Exception:
            # Friendly error message without traceback
            Clock.schedule_once(lambda dt: self.append_log('[color=ff3333]Failed to fetch qualities. Check URL or connection.[/color]'), 0)

    def _update_formats_in_ui(self, formats):
        self.quality_list = formats if formats else []
        try:
            self.ids.quality_spinner.text = 'Select quality'
        except Exception:
            pass

    def on_download_button(self):
        if self.downloading:
            self.append_log('[b]Already downloading. Please wait...[/b]')
            return
        url = self.ids.url_input.text.strip() if 'url_input' in self.ids else ''
        if not url:
            self.append_log('[color=ff3333]Please enter a video URL.[/color]')
            return
        quality = self.ids.quality_spinner.text if 'quality_spinner' in self.ids else 'Select quality'
        if quality == 'Select quality' or not quality:
            self.append_log('[color=ff3333]Please select a quality.[/color]')
            return

        self.selected_format_id = quality.split(' - ')[0].strip()
        self.save_path = (self.ids.path_input.text.strip() or get_default_download_path()) if 'path_input' in self.ids else get_default_download_path()
        try:
            os.makedirs(self.save_path, exist_ok=True)
        except Exception as e:
            self.append_log(f'[color=ff3333]Cannot create directory: {e}[/color]')
            return

        self.progress = 0
        self.status = 'Starting download...'
        self.downloading = True
        threading.Thread(target=self._download_thread, args=(url,), daemon=True).start()

    def _update_from_hook(self, state, downloaded_bytes, total_bytes):
        try:
            if total_bytes and total_bytes > 0:
                self.progress = min(1.0, float(downloaded_bytes) / float(total_bytes))
                self.status = f"{int(self.progress * 100)}% - {state}"
            else:
                self.status = state
        except Exception:
            self.status = state

    def _download_thread(self, url):
        try:
            def progress_hook(d):
                try:
                    status = d.get('status')
                    if status == 'downloading':
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        Clock.schedule_once(lambda dt: self._update_from_hook('downloading', downloaded, total), 0)
                    elif status == 'finished':
                        Clock.schedule_once(lambda dt: self.append_log('[b]Download finished (processing)...[/b]'), 0)
                except Exception:
                    pass

            fmt = self.selected_format_id or ''
            if fmt and (fmt.isdigit() or '+' in fmt or '/' in fmt):
                format_option = f"{fmt}+bestaudio/best"
            else:
                format_option = "bestvideo+bestaudio/best"

            ydl_opts = {
                    'format': format_option,  # Best video + best audio, merged
                    'merge_output_format': 'mp4',          # Final output format
                    'outtmpl': os.path.join(self.save_path, '%(title)s.%(ext)s'),  # Save in downloads folder
                    'quiet': True,                          # No verbose logs
                    'noplaylist': True,                     # Single video only
                    'progress_hooks': [progress_hook],
                    'postprocessors': [{                    # Merge video & audio
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4'
                    }]
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([url])

            if result != 0:
                Clock.schedule_once(lambda dt: self.append_log('[color=ff3333]Download failed. Check URL or connection.[/color]'), 0)
                Clock.schedule_once(lambda dt: setattr(self, 'status', 'Error'), 0)
            else:
                Clock.schedule_once(lambda dt: self.append_log('[color=22aa22]Download completed successfully.[/color]'), 0)
                Clock.schedule_once(lambda dt: setattr(self, 'status', 'Completed'), 0)
                Clock.schedule_once(lambda dt: setattr(self, 'progress', 1.0), 0)

        except Exception:
            Clock.schedule_once(lambda dt: self.append_log('[color=ff3333]Download failed. Check URL or connection.[/color]'), 0)
            Clock.schedule_once(lambda dt: setattr(self, 'status', 'Error'), 0)

        finally:
            Clock.schedule_once(lambda dt: setattr(self, 'downloading', False), 0)

    def fetch_qualities(self):
        url = self.ids.url_input.text.strip() if 'url_input' in self.ids else ''
        if not url:
            self.append_log('[color=ff3333]Please enter a URL[/color]')
            return

        # Show loading popup
        self.loading_popup = Popup(
            title="Loading",
            content=Label(text="Fetching qualities...\nPlease wait."),
            size_hint=(0.5, 0.3),
            auto_dismiss=False
        )
        self.loading_popup.open()

        self.append_log('Fetching available formats...')
        threading.Thread(target=self._fetch_qualities_thread, args=(url,), daemon=True).start()

    def _fetch_qualities_thread(self, url):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = []
            seen = set()
            for f in info.get('formats', []):
                if f.get('vcodec') and f.get('vcodec') != 'none':
                    fid = f.get('format_id') or str(f.get('tbr') or f.get('height') or f.get('width') or '')
                    note = f.get('format_note') or (f.get('height') and f"{f.get('height')}p") or ''
                    ext = f.get('ext') or ''
                    display_parts = [p for p in (fid, note, ext) if p]
                    display = " - ".join(display_parts)
                    if display not in seen:
                        seen.add(display)
                        formats.append(display)

            Clock.schedule_once(lambda dt: self._show_quality_popup(formats), 0)

        except Exception:
            Clock.schedule_once(lambda dt: self.append_log('[color=ff3333]Failed to fetch qualities. Check URL or connection.[/color]'), 0)
            Clock.schedule_once(lambda dt: self.loading_popup.dismiss(), 0)

    def _show_quality_popup(self, formats):
        # Close loading popup
        if hasattr(self, 'loading_popup'):
            self.loading_popup.dismiss()

        if not formats:
            self.append_log('[color=ff3333]No video formats found.[/color]')
            return

        self.quality_list = formats
        self.ids.quality_spinner.text = formats[0]

        # Create popup with Spinner
        spinner = Spinner(text="Expand Quality", values=formats, size_hint_y=None, height='40dp')

        def select_quality(spinner_instance, text):
            self.ids.quality_spinner.text = text
            popup.dismiss()

        spinner.bind(text=select_quality)

        popup = Popup(
            title="Select Video Quality",
            content=spinner,
            size_hint=(0.6, 0.4),
            auto_dismiss=True
        )
        popup.open()

        self.append_log('Available qualities fetched.')
    


class VideoDownloaderApp(App):
    def build(self):
        Builder.load_string(KV)
        main_ui = MainUI()
              
        return main_ui


if __name__ == '__main__':
    VideoDownloaderApp().run()
