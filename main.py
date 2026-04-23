import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Real-Time Stress Test")
        self.geometry("1200x800")

        self.tempos = []
        self.stats = {}
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        # Sidebar de Configurações
        self.sidebar = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="⚙️ Parâmetros", font=("Roboto", 20, "bold")).pack(pady=15)

        self.entry_query = self.create_input("Query SQL:", "SELECT 1 + 1", True)
        self.entry_total = self.create_input("Total de Requisições:", "1000")
        self.entry_concur = self.create_input("Simultâneas (Concurrency):", "50")
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
        self.lbl_status.pack(pady=5)
        
        self.lbl_media = ctk.CTkLabel(self.sidebar, text="Média: ---", font=("Roboto", 18, "bold"))
        self.lbl_media.pack(pady=10)

        # Área Principal do Gráfico
        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.fig.patch.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_content)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_input(self, label, default, is_text=False):
        ctk.CTkLabel(self.sidebar, text=label).pack(anchor="w", padx=20)
        if is_text:
            el = ctk.CTkTextbox(self.sidebar, height=60, width=250)
            el.insert("0.0", default)
        else:
            el = ctk.CTkEntry(self.sidebar, width=250)
            el.insert(0, default)
        el.pack(pady=5, padx=20)
        return el

    def update_plot_live(self):
        """Atualiza o gráfico a cada 1 segundo (1000ms)."""
        if not self.is_running and not self.tempos:
            return

        self.ax.clear()
        self.ax.set_title("Desempenho em Tempo Real (ms)", color="white", pad=20)
        
        if self.tempos:
            # Plotando apenas os dados coletados até agora
            self.ax.plot(self.tempos, color="#3b8ed0", linewidth=1.2)
            self.ax.relim()
            self.ax.autoscale_view()

        self.ax.set_xlabel("Requisições Concluídas", color="white")
        self.ax.set_ylabel("Latência (ms)", color="white")
        self.ax.tick_params(colors='white')
        self.ax.grid(True, linestyle='--', alpha=0.1)
        self.canvas.draw()

        # Agenda a próxima atualização para daqui a 1000ms (1 segundo)
        if self.is_running:
            self.after(1000, self.update_plot_live)

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            self.fig.savefig(file_path, facecolor=self.fig.get_facecolor(), bbox_inches='tight')
            self.lbl_status.configure(text="💾 Relatório salvo!", text_color="green")

    def stop_test(self):
        self.stop_event.set()
        self.is_running = False
        self.lbl_status.configure(text="🛑 Parando...", text_color="orange")

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                if self.stop_event.is_set(): return
                async with sem:
                    if self.stop_event.is_set(): return
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query)
                                await cur.fetchone()
                        self.tempos.append((time.perf_counter() - start) * 1000)
                    except:
                        self.tempos.append(0)

            tasks = [task() for _ in range(int(total))]
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set(): break
                await f
            
            pool.close()
            await pool.wait_closed()
            
            self.is_running = False
            validos = [t for t in self.tempos if t > 0]
            if validos:
                self.stats = {
                    'query': query, 'total': total, 'concur': concur,
                    'avg': sum(validos)/len(validos), 'min': min(validos), 'max': max(validos)
                }
                # Legenda final com estatísticas
                info_text = (f"Média: {self.stats['avg']:.2f}ms\n"
                            f"Mín: {self.stats['min']:.2f}ms\n"
                            f"Máx: {self.stats['max']:.2f}ms")
                
                self.ax.text(0.98, 0.98, info_text, transform=self.ax.transAxes, 
                            verticalalignment='top', horizontalalignment='right', 
                            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7), 
                            color='white', fontsize=10)
                self.lbl_media.configure(text=f"Média: {self.stats['avg']:.2f}ms")
            
            self.update_plot_live() # Atualização final
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(text="✅ Concluído!", text_color="green")

        except Exception:
            self.lbl_status.configure(text="❌ Erro de Conexão", text_color="red")
            self.is_running = False
        
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def start_test_thread(self):
        # Limpa dados anteriores
        self.tempos = []
        self.stats = {}
        self.ax.clear()
        self.canvas.draw()
        
        self.is_running = True
        self.stop_event.clear()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.lbl_status.configure(text="🚀 Executando...", text_color="cyan")
        
        args = (
            self.entry_query.get("0.0", "end").strip(),
            self.entry_total.get(),
            self.entry_concur.get(),
            self.entry_host.get(),
            self.entry_user.get(),
            self.entry_pass.get(),
            self.entry_db.get()
        )

        # Inicia o loop de atualização (agora a cada 1000ms)
        self.update_plot_live()
        
        # Dispara o processo assíncrono em uma thread separada
        threading.Thread(target=lambda: asyncio.run(self.run_stress_test(*args)), daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
