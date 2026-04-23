import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog
import textwrap # Para quebrar o texto da query

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Pro Stress Test - Smooth Edition")
        self.geometry("1250x850")

        self.tempos = []
        self.stats = {}
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="⚙️ Parâmetros", font=("Roboto", 20, "bold")).pack(pady=15)

        self.entry_query = self.create_input("Query SQL (até 500 chars):", "SELECT 1 + 1", True)
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
        self.lbl_status.pack(pady=5)
        
        self.lbl_media = ctk.CTkLabel(self.sidebar, text="Média: ---", font=("Roboto", 18, "bold"))
        self.lbl_media.pack(pady=10)

        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.fig.patch.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main_content)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_input(self, label, default, is_text=False):
        ctk.CTkLabel(self.sidebar, text=label).pack(anchor="w", padx=20)
        if is_text:
            el = ctk.CTkTextbox(self.sidebar, height=80, width=250)
            el.insert("0.0", default)
        else:
            el = ctk.CTkEntry(self.sidebar, width=250)
            el.insert(0, default)
        el.pack(pady=5, padx=20)
        return el

    def moving_average(self, data, window=10):
        """Calcula a média móvel para suavizar o gráfico."""
        if len(data) < window: return data
        return [sum(data[i:i+window])/window for i in range(len(data)-window+1)]

    def update_plot_live(self):
        if not self.is_running and not self.tempos: return

        self.ax.clear()
        self.ax.set_title("Desempenho (Linha Suavizada)", color="white", pad=25)
        
        if self.tempos:
            # Plota os dados reais (fundo, mais claro)
            self.ax.plot(self.tempos, color="#3b8ed0", alpha=0.3, linewidth=0.5)
            # Plota a média móvel (suavizada)
            suave = self.moving_average(self.tempos, window=15)
            self.ax.plot(suave, color="#5dade2", linewidth=2)
            
            self.ax.relim()
            self.ax.autoscale_view()

        self.ax.set_xlabel("Requisições", color="white")
        self.ax.set_ylabel("ms", color="white")
        self.ax.tick_params(colors='white')
        self.ax.grid(True, linestyle='--', alpha=0.1)
        self.canvas.draw()

        if self.is_running:
            self.after(1000, self.update_plot_live)

    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if file_path:
            self.fig.savefig(file_path, facecolor=self.fig.get_facecolor(), bbox_inches='tight', dpi=150)
            self.lbl_status.configure(text="💾 Relatório salvo!", text_color="green")

    def stop_test(self):
        self.stop_event.set()
        self.is_running = False

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                if self.stop_event.is_set(): return
                async with sem:
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query)
                                await cur.fetchone()
                        self.tempos.append((time.perf_counter() - start) * 1000)
                    except: self.tempos.append(0)

            tasks = [task() for _ in range(int(total))]
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set(): break
                await f
            
            pool.close()
            await pool.wait_closed()
            
            self.is_running = False
            validos = [t for t in self.tempos if t > 0]
            if validos:
                # Tratar a query para exibição (limite 500 chars e quebra de linha)
                query_limpa = query[:500] + "..." if len(query) > 500 else query
                query_wrap = "\n".join(textwrap.wrap(query_limpa, width=60))
                
                self.stats = {
                    'query': query_wrap, 'avg': sum(validos)/len(validos),
                    'min': min(validos), 'max': max(validos), 'total': total, 'concur': concur
                }
                
                info_text = (f"STATS:\n{self.stats['query']}\n\n"
                            f"Total: {total} | Conc: {concur}\n"
                            f"Média: {self.stats['avg']:.2f}ms\n"
                            f"Mín/Máx: {self.stats['min']:.2f}ms / {self.stats['max']:.2f}ms")
                
                self.ax.text(1.02, 0.5, info_text, transform=self.ax.transAxes, 
                            verticalalignment='center', horizontalalignment='left', 
                            bbox=dict(boxstyle='round', facecolor='black', alpha=0.8), 
                            color='white', fontsize=9)
                self.lbl_media.configure(text=f"Média: {self.stats['avg']:.2f}ms")
            
            self.update_plot_live()
            self.btn_save.configure(state="normal")
            self.lbl_status.configure(text="✅ Concluído!", text_color="green")

        except Exception:
            self.lbl_status.configure(text="❌ Erro Conexão", text_color="red")
            self.is_running = False
        
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def start_test_thread(self):
        self.tempos = []; self.stats = {}; self.ax.clear(); self.canvas.draw()
        self.is_running = True; self.stop_event.clear()
        self.btn_start.configure(state="disabled"); self.btn_stop.configure(state="normal")
        self.btn_save.configure(state="disabled")
        
        args = (
            self.entry_query.get("0.0", "end").strip(),
            self.entry_total.get(), self.entry_concur.get(),
            self.entry_host.get(), self.entry_user.get(),
            self.entry_pass.get(), self.entry_db.get()
        )
        self.update_plot_live()
        threading.Thread(target=lambda: asyncio.run(self.run_stress_test(*args)), daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
