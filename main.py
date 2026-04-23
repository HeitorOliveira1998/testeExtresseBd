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

        self.title("MySQL Stress Test Pro")
        self.geometry("1150x800")

        self.tempos = []
        self.stats = {} # Dicionário para guardar estatísticas do último teste
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
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

        self.btn_save = ctk.CTkButton(self.sidebar, text="💾 SALVAR GRÁFICO + INFO", command=self.save_graph, fg_color="#444444", state="disabled")
        self.btn_save.pack(pady=5, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Status: Pronto", text_color="gray")
        self.lbl_status.pack(pady=5)
        
        self.lbl_media = ctk.CTkLabel(self.sidebar, text="Média: ---", font=("Roboto", 18, "bold"))
        self.lbl_media.pack(pady=10)

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

    def update_graph(self):
        self.ax.clear()
        self.ax.set_title("Resultado do Stress Test", color="white", fontsize=14, pad=20)
        
        # Plotagem dos dados
        self.ax.plot(self.tempos, color="#3b8ed0", linewidth=1, label="Latência")
        
        # Se houver estatísticas, adicionamos uma caixa de texto no gráfico
        if self.stats:
            info_text = (
                f"Query: {self.stats['query'][:40]}...\n"
                f"Total Reqs: {self.stats['total']}\n"
                f"Simultâneas: {self.stats['concur']}\n"
                f"Mín: {self.stats['min']:.2f}ms | Máx: {self.stats['max']:.2f}ms\n"
                f"Média: {self.stats['avg']:.2f}ms"
            )
            # Posiciona o texto no canto superior direito do gráfico
            self.ax.text(0.98, 0.98, info_text, transform=self.ax.transAxes,
                        verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='black', alpha=0.5),
                        color='white', fontsize=9)

        self.ax.set_xlabel("Número da Requisição", color="white")
        self.ax.set_ylabel("ms", color="white")
        self.ax.tick_params(colors='white')
        self.ax.grid(True, linestyle='--', alpha=0.2)
        self.canvas.draw()

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            title="Salvar Relatório de Stress Test"
        )
        if file_path:
            # Salva a figura com as estatísticas que já estão nela
            self.fig.savefig(file_path, facecolor=self.fig.get_facecolor(), bbox_inches='tight')
            self.lbl_status.configure(text="💾 Relatório salvo!", text_color="green")

    def stop_test(self):
        self.stop_event.set()
        self.lbl_status.configure(text="🛑 Parando...", text_color="orange")

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        self.tempos = []
        self.stop_event.clear()
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
            
            if self.tempos:
                # Filtrar valores zero (falhas) para não estragar a média/mínimo
                validos = [t for t in self.tempos if t > 0]
                if validos:
                    self.stats = {
                        'query': query,
                        'total': total,
                        'concur': concur,
                        'avg': sum(validos) / len(validos),
                        'min': min(validos),
                        'max': max(validos)
                    }
                    self.lbl_media.configure(text=f"Média: {self.stats['avg']:.2f}ms")
                
            self.update_graph()
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(text="✅ Concluído!", text_color="green")

        except Exception as e:
            self.lbl_status.configure(text="❌ Erro de Conexão", text_color="red")
        
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def start_test_thread(self):
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.stats = {}
        
        args = (
            self.entry_query.get("0.0", "end").strip(),
            self.entry_total.get(),
            self.entry_concur.get(),
            self.entry_host.get(),
            self.entry_user.get(),
            self.entry_pass.get(),
            self.entry_db.get()
        )

        threading.Thread(target=lambda: asyncio.run(self.run_stress_test(*args)), daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
