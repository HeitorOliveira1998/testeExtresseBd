import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog
import textwrap

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Stress Test - Visual Report Edition")
        self.geometry("1300x850")

        self.tempos = []
        self.falhas = 0
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="⚙️ CONFIGURAÇÕES", font=("Roboto", 20, "bold")).pack(pady=15)

        self.entry_query = self.create_input("Query SQL:", "SELECT 1 + 1", True)
        self.entry_total = self.create_input("Total de Requisições:", "1000")
        self.entry_concur = self.create_input("Simultâneas:", "50")
        self.entry_host = self.create_input("Host MySQL:", "127.0.0.1")
        self.entry_user = self.create_input("Usuário:", "root")
        
        self.entry_pass = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Senha", show="*")
        self.entry_pass.pack(pady=5, padx=20)
        
        self.entry_db = self.create_input("Banco de Dados:", "mysql")

        self.btn_start = ctk.CTkButton(self.sidebar, text="🔥 INICIAR TESTE", command=self.start_test_thread, fg_color="green", font=("Roboto", 14, "bold"))
        self.btn_start.pack(pady=(20, 5), padx=20)

        self.btn_stop = ctk.CTkButton(self.sidebar, text="🛑 PARAR", command=self.stop_test, fg_color="red", state="disabled")
        self.btn_stop.pack(pady=5, padx=20)

        self.btn_save = ctk.CTkButton(self.sidebar, text="💾 SALVAR RELATÓRIO", command=self.save_graph, fg_color="#444444", state="disabled")
        self.btn_save.pack(pady=5, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Status: Pronto", text_color="gray")
        self.lbl_status.pack(pady=10)

        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.fig.patch.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_content)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_input(self, label, default, is_text=False):
        ctk.CTkLabel(self.sidebar, text=label).pack(anchor="w", padx=20)
        el = ctk.CTkTextbox(self.sidebar, height=80, width=250) if is_text else ctk.CTkEntry(self.sidebar, width=250)
        el.insert("0.0" if is_text else 0, default)
        el.pack(pady=5, padx=20)
        return el

    def update_plot(self):
        """Atualiza o gráfico e desenha as estatísticas dentro dele."""
        self.ax.clear()
        self.ax.set_title("Relatório de Latência MySQL", color="white", fontcenter=16, pad=30)
        
        validos = [t for t in self.tempos if t > 0]
        
        if self.tempos:
            # Plotagem principal
            self.ax.plot(self.tempos, color="#3b8ed0", alpha=0.3, linewidth=0.8, label="Bruto")
            if len(self.tempos) > 10:
                suave = [sum(self.tempos[max(0, i-10):i+1])/len(self.tempos[max(0, i-10):i+1]) for i in range(len(self.tempos))]
                self.ax.plot(suave, color="#5dade2", linewidth=2, label="Tendência (Média Móvel)")

            # BLOCO DE TEXTO DENTRO DO GRÁFICO
            if validos:
                v_min, v_max, v_avg = min(validos), max(validos), sum(validos)/len(validos)
                stats_txt = (f"Média: {v_avg:.2f} ms\n"
                            f"Mínimo: {v_min:.2f} ms\n"
                            f"Máximo: {v_max:.2f} ms\n"
                            f"Falhas: {self.falhas}")
                
                # Caixa de texto no canto superior esquerdo
                self.ax.text(0.02, 0.95, stats_txt, transform=self.ax.transAxes, 
                            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='black', alpha=0.7),
                            color='white', fontfamily='monospace', fontsize=10)

                # Query no rodapé do gráfico (apenas quando houver espaço)
                query_full = self.entry_query.get("0.0", "end").strip()
                query_short = textwrap.fill(query_full[:500], width=80)
                self.fig.text(0.5, 0.02, f"Query: {query_short}", ha='center', color='gray', fontsize=8, style='italic')

        self.ax.set_xlabel("Requisições Concluídas", color="white")
        self.ax.set_ylabel("Tempo de Resposta (ms)", color="white")
        self.ax.tick_params(colors='white')
        self.ax.grid(True, linestyle='--', alpha=0.1)
        self.fig.tight_layout(rect=[0, 0.05, 1, 0.95]) # Ajusta margens para caber o rodapé
        self.canvas.draw()

    def update_loop(self):
        if self.is_running:
            self.update_plot()
            self.after(1000, self.update_loop)

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                if self.stop_event.is_set(): return
                async with sem:
                    t_start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query); await cur.fetchone()
                        self.tempos.append((time.perf_counter() - t_start) * 1000)
                    except:
                        self.falhas += 1
                        self.tempos.append(0)

            tasks = [task() for _ in range(int(total))]
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set(): break
                await f
            
            pool.close(); await pool.wait_closed()
            self.is_running = False
            self.update_plot() # Refresh final com todos os dados
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(text="✅ Concluído!", text_color="green")

        except Exception:
            self.lbl_status.configure(text="❌ Erro Conexão", text_color="red")
            self.is_running = False
        
        self.btn_start.configure(state="normal"); self.btn_stop.configure(state="disabled")

    def save_graph(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.fig.savefig(path, facecolor=self.fig.get_facecolor(), bbox_inches='tight', dpi=150)

    def stop_test(self):
        self.stop_event.set(); self.is_running = False

    def start_test_thread(self):
        self.tempos = []; self.falhas = 0; self.is_running = True; self.stop_event.clear()
        self.btn_start.configure(state="disabled"); self.btn_stop.configure(state="normal"); self.btn_save.configure(state="disabled")
        self.lbl_status.configure(text="🚀 Rodando...", text_color="cyan")
        
        args = (self.entry_query.get("0.0", "end").strip(), self.entry_total.get(), self.entry_concur.get(), 
                self.entry_host.get(), self.entry_user.get(), self.entry_pass.get(), self.entry_db.get())
        
        self.update_loop() # Inicia atualização visual
        threading.Thread(target=lambda: asyncio.run(self.run_stress_test(*args)), daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
