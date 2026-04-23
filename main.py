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

        self.title("MySQL Stress Test - Real Time Fix")
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
        if is_text:
            el = ctk.CTkTextbox(self.sidebar, height=80, width=250)
            el.insert("0.0", default)
        else:
            el = ctk.CTkEntry(self.sidebar, width=250)
            el.insert(0, default)
        el.pack(pady=5, padx=20)
        return el

    def update_plot(self):
        """Renderiza o gráfico e as estatísticas. Chamado periodicamente via after()."""
        if not self.is_running and not self.tempos:
            return

        self.ax.clear()
        self.ax.set_title("Relatório de Latência MySQL", color="white", pad=30)
        
        validos = [t for t in self.tempos if t > 0]
        
        if self.tempos:
            # Plotagem principal (dados brutos e tendência)
            self.ax.plot(self.tempos, color="#3b8ed0", alpha=0.3, linewidth=0.8)
            if len(self.tempos) > 10:
                # Média móvel simples
                suave = [sum(self.tempos[max(0, i-10):i+1])/len(self.tempos[max(0, i-10):i+1]) for i in range(len(self.tempos))]
                self.ax.plot(suave, color="#5dade2", linewidth=2)

            # Caixa de texto interna com Stats
            if validos:
                v_min, v_max, v_avg = min(validos), max(validos), sum(validos)/len(validos)
                stats_txt = (f"Média: {v_avg:.2f} ms\n"
                            f"Mínimo: {v_min:.2f} ms\n"
                            f"Máximo: {v_max:.2f} ms\n"
                            f"Falhas: {self.falhas}")
                
                self.ax.text(0.02, 0.95, stats_txt, transform=self.ax.transAxes, 
                            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='black', alpha=0.7),
                            color='white', fontfamily='monospace', fontsize=10)

        self.ax.set_xlabel("Requisições Concluídas", color="white")
        self.ax.set_ylabel("Tempo de Resposta (ms)", color="white")
        self.ax.tick_params(colors='white')
        self.ax.grid(True, linestyle='--', alpha=0.1)
        self.canvas.draw()

        # Continua o loop de atualização se ainda estiver rodando
        if self.is_running:
            self.after(1000, self.update_plot)

    def stop_test(self):
        """Sinaliza a parada imediata."""
        self.stop_event.set()
        self.is_running = False
        self.lbl_status.configure(text="🛑 Parada solicitada...", text_color="orange")

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306, 'connect_timeout': 5}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))

            async def task():
                # Check crítico de parada antes de iniciar a task
                if self.stop_event.is_set():
                    return

                async with sem:
                    if self.stop_event.is_set(): return
                    t_start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query)
                                await cur.fetchone()
                        self.tempos.append((time.perf_counter() - t_start) * 1000)
                    except:
                        self.falhas += 1
                        self.tempos.append(0)

            # Criar lista de tarefas
            tasks = [task() for _ in range(int(total))]
            
            # Executar de forma que possamos interromper o lote
            for next_task in asyncio.as_completed(tasks):
                if self.stop_event.is_set():
                    break
                await next_task

            pool.close()
            await pool.wait_closed()

        except Exception as e:
            self.lbl_status.configure(text=f"❌ Erro: {str(e)[:20]}", text_color="red")
        
        # Finalização da UI (precisa ser via after para ser thread-safe)
        self.after(0, self.finalize_ui)

    def finalize_ui(self):
        self.is_running = False
        self.update_plot() # Desenho final
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_save.configure(state="normal")
        
        status_txt = "🛑 Interrompido" if self.stop_event.is_set() else "✅ Concluído"
        color = "orange" if self.stop_event.is_set() else "green"
        self.lbl_status.configure(text=status_txt, text_color=color)

    def start_test_thread(self):
        # Reset de variáveis
        self.tempos = []
        self.falhas = 0
        self.is_running = True
        self.stop_event.clear()
        
        # Configuração da UI
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_save.configure(state="disabled")
        self.lbl_status.configure(text="🚀 Rodando...", text_color="cyan")
        
        args = (
            self.entry_query.get("0.0", "end").strip(),
            self.entry_total.get(),
            self.entry_concur.get(),
            self.entry_host.get(),
            self.entry_user.get(),
            self.entry_pass.get(),
            self.entry_db.get()
        )
        
        # Inicia o ciclo de vida: Gráfico e Thread de Processamento
        self.update_plot()
        
        def start_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_stress_test(*args))
            loop.close()

        threading.Thread(target=start_async_loop, daemon=True).start()

    def save_graph(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            # Adiciona a query no rodapé antes de salvar definitivamente
            query_full = self.entry_query.get("0.0", "end").strip()
            query_short = textwrap.fill(query_full[:500], width=80)
            self.fig.text(0.5, 0.01, f"Query: {query_short}", ha='center', color='gray', fontsize=7)
            self.fig.savefig(path, facecolor=self.fig.get_facecolor(), bbox_inches='tight', dpi=150)

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
