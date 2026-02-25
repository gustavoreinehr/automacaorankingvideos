import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sys
import threading
import os
import subprocess
from pathlib import Path

# Importa o script principal
import main

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str):
        self.widget.configure(state="normal")
        self.widget.insert("end", str, (self.tag,))
        self.widget.see("end")
        self.widget.configure(state="disabled")
        # Força atualização da interface
        self.widget.update_idletasks()

    def flush(self):
        pass

class MusicAutomationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Vídeos Virais - Music Ranking")
        self.root.geometry("700x550")
        self.root.configure(bg="#1e1e1e")

        # Estilos
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="white", font=("Segoe UI", 12))
        style.configure("TButton", font=("Segoe UI", 11, "bold"), background="#3a3a3a", foreground="white", borderwidth=0)
        style.map("TButton", background=[('active', '#505050')])

        # Container Principal
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Cabeçalho
        header_label = ttk.Label(main_frame, text="🎬 Automação de Rankings Musicais", font=("Segoe UI", 18, "bold"))
        header_label.pack(pady=(0, 20))

        # Botões de Ação
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.btn_run = tk.Button(btn_frame, text="▶ INICIAR GERAÇÃO", command=self.start_thread, 
                                 bg="#007acc", fg="white", font=("Segoe UI", 12, "bold"), 
                                 relief="flat", padx=20, pady=10, cursor="hand2")
        self.btn_run.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_open = tk.Button(btn_frame, text="📂 Abrir Pasta de Saída", command=self.open_output, 
                                  bg="#2d2d2d", fg="white", font=("Segoe UI", 11), 
                                  relief="flat", padx=20, pady=10, cursor="hand2")
        self.btn_open.pack(side=tk.LEFT)

        # Área de Log
        log_label = ttk.Label(main_frame, text="Progresso:", font=("Segoe UI", 10))
        log_label.pack(anchor="w", pady=(5, 0))

        self.log_area = scrolledtext.ScrolledText(main_frame, state='disabled', height=15, 
                                                  bg="#252526", fg="#d4d4d4", font=("Consolas", 10), borderwidth=0)
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Tags para colorir o log
        self.log_area.tag_config("stdout", foreground="#d4d4d4")
        self.log_area.tag_config("stderr", foreground="#ff6b6b")

        # Redirecionar stdout e stderr
        sys.stdout = TextRedirector(self.log_area, "stdout")
        sys.stderr = TextRedirector(self.log_area, "stderr")

        # Footer
        footer_label = ttk.Label(main_frame, text="Powered by Groq AI & FFmpeg", font=("Segoe UI", 8), foreground="#666")
        footer_label.pack(anchor="e", pady=(10, 0))

    def start_thread(self):
        # Desabilita botão para evitar cliques duplos
        self.btn_run.config(state="disabled", bg="#555")
        self.log_area.configure(state="normal")
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state="disabled")
        
        # Roda em thread separada para não travar a interface
        thread = threading.Thread(target=self.run_automation)
        thread.daemon = True
        thread.start()

    def run_automation(self):
        try:
            print("🚀 Iniciando o motor da IA...")
            # Chama a função main do script original
            main.main()
            print("
✨ PROCESSO FINALIZADO COM SUCESSO! ✨")
            messagebox.showinfo("Sucesso", "Vídeo gerado com sucesso! Verifique a pasta output.")
        except Exception as e:
            print(f"
❌ ERRO CRÍTICO: {e}")
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
        finally:
            # Reabilita o botão
            self.root.after(0, lambda: self.btn_run.config(state="normal", bg="#007acc"))

    def open_output(self):
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        
        if sys.platform == 'win32':
            os.startfile(output_path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.call(('open', output_path))
        else:  # linux
            subprocess.call(('xdg-open', output_path))

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicAutomationApp(root)
    root.mainloop()
