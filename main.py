import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog, messagebox
import textwrap
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Optimization Comparator (A/B Test)")
        self.geometry("1400x900")

        self.data_sessao_1 = []
        self.data_sessao_2 = []
        self.sessao_atual = 1
        
        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="🚀 COMPARADOR DE QUERY", font=("Roboto", 20, "bold")).pack(pady=15)

        self.seg_control = ctk.CTkSegmentedButton(self.sidebar, values=["Execução 1", "Execução 2"],
                                                 command=self.trocar_sessao)
        self.seg_control.set("Execução 1")
        self.seg_control.pack(pady=10, padx=20, fill="x")

        self.entry_query = self.create_input("Query SQL:", "SELECT * FROM tabela -- Query 1", True)
        self.entry_total = self.create_input("Total de Requisições:", "500")
        self.entry_concur = self.create_input("Simultâneas:", "20")
        self.entry_host = self.create_input("Host:", "127.0.0.1")
        self.entry_user = self.create_input("Usuário:", "root")
        self.entry_pass = ctk.CTkEntry(self.sidebar, width=250, placeholder_text="Senha", show="*")
        self.entry_pass.pack(pady=5, padx=20)
        self.entry_db = self.create_input("Banco:", "mysql")

        self.btn_start = ctk.CTkButton(self.sidebar, text="🔥 INICIAR SESSÃO", command=self.start_test_thread, fg_color="green")
        self.btn_start.pack(pady=10, padx=20)

        self.btn_stop = ctk.CTkButton(self.sidebar, text="🛑 PARAR", command=self.stop_test, fg_color="red", state="disabled")
        self.btn_stop.pack(pady=5, padx=20)

        self.btn_save = ctk.CTkButton(self.sidebar, text="💾 EXPORTAR TODOS OS GRÁFICOS", command=self.save_all_graphs, fg_color="#444444")
        self.btn_save.pack(pady=5, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Pronto para Execução 1", text_color="gray")
        self.lbl_status.pack(pady=10)

        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.tabview = ctk.CTkTabview(self.main_content)
        self.tabview.pack(fill="both", expand=True)
        self.tabview.add("Sessão 1")
        self.tabview.add("Sessão 2")
        self.tabview.add("COMPARATIVO")

        self.setup_plots()

    def setup_plots(self):
        self.figs = {}; self.canvas = {}; self.axs = {}
        for tab in ["Sessão 1", "Sessão 2", "COMPARATIVO"]:
            fig = Figure(figsize=(8, 6), dpi=100)
            fig.patch.set_facecolor('#1e1e1e')
            ax = fig.add_subplot(111)
            ax.set_facecolor('#1e1e1e')
            ax.tick_params(colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['top'].set_color('white') 
            ax.spines['right'].set_color('white')
            ax.spines['left'].set_color('white')
            
            canv = FigureCanvasTkAgg(fig, master=self.tabview.tab(tab))
            canv.get_tk_widget().pack(fill="both", expand=True)
            
            self.figs[tab] = fig; self.axs[tab] = ax; self.canvas[tab] = canv

    def create_input(self, label, default, is_text=False):
        ctk.CTkLabel(self.sidebar, text=label).pack(anchor="w", padx=20)
        el = ctk.CTkTextbox(self.sidebar, height=70, width=250) if is_text else ctk.CTkEntry(self.sidebar, width=250)
        el.insert("0.0" if is_text else 0, default)
        el.pack(pady=5, padx=20)
        return el

    def trocar_sessao(self, value):
        self.sessao_atual = 1 if value == "Execução 1" else 2

    def update_plots_live(self):
        if not self.is_running: return
        tab_name = f"Sessão {self.sessao_atual}"
        data = self.data_sessao_1 if self.sessao_atual == 1 else self.data_sessao_2
        color = "#e74c3c" if self.sessao_atual == 1 else "#2ecc71"

        ax = self.axs[tab_name]
        ax.clear()
        ax.set_title(f"Performance - {tab_name}", color="white")
        if data:
            ax.plot(data, color=color, linewidth=1)
        self.canvas[tab_name].draw()
        
        self.update_comparativo()
        if self.is_running: self.after(1000, self.update_plots_live)

    def update_comparativo(self):
        ax = self.axs["COMPARATIVO"]
        ax.clear()
        ax.set_title("Antes (Vermelho) vs Depois (Verde)", color="white")
        
        if self.data_sessao_1:
            ax.plot(self.data_sessao_1, color="#e74c3c", alpha=0.5, label="Antes (Sessão 1)")
        if self.data_sessao_2:
            ax.plot(self.data_sessao_2, color="#2ecc71", alpha=0.8, label="Depois (Sessão 2)")
        
        if self.data_sessao_1 and self.data_sessao_2:
            m1 = sum(self.data_sessao_1)/len(self.data_sessao_1)
            m2 = sum(self.data_sessao_2)/len(self.data_sessao_2)
            ganho = ((m1 - m2) / m1) * 100 if m1 > 0 else 0
            res_txt = f"Ganho de Performance: {ganho:.1f}%" if ganho > 0 else f"Perda: {abs(ganho):.1f}%"
            ax.text(0.5, 0.95, res_txt, transform=ax.transAxes, ha='center', color='yellow', fontweight='bold', bbox=dict(facecolor='black', alpha=0.5))

        ax.legend(); self.canvas["COMPARATIVO"].draw()

    def save_all_graphs(self):
        # Abre diálogo para selecionar pasta e nome base
        file_path = filedialog.asksaveasfilename(
            title="Salvar relatórios (serão gerados 3 arquivos)",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")]
        )
        
        if not file_path: return

        # Separa o caminho e o nome base
        dirname = os.path.dirname(file_path)
        basename = os.path.basename(file_path).replace(".png", "")

        try:
            # Salva os 3 arquivos individualmente
            self.figs["Sessão 1"].savefig(f"{dirname}/{basename}_antes.png", facecolor='#1e1e1e', dpi=150)
            self.figs["Sessão 2"].savefig(f"{dirname}/{basename}_depois.png", facecolor='#1e1e1e', dpi=150)
            self.figs["COMPARATIVO"].savefig(f"{dirname}/{basename}_comparativo.png", facecolor='#1e1e1e', dpi=150)
            
            messagebox.showinfo("Sucesso", f"Os 3 gráficos foram salvos em:\n{dirname}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar arquivos: {e}")

    def stop_test(self):
        self.stop_event.set(); self.is_running = False

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))
            target_list = self.data_sessao_1 if self.sessao_atual == 1 else self.data_sessao_2

            async def task():
                async with sem:
                    if self.stop_event.is_set(): return
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query); await cur.fetchone()
                        target_list.append((time.perf_counter() - start) * 1000)
                    except: target_list.append(0)

            tasks = [task() for _ in range(int(total))]
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set(): break
                await f
            pool.close(); await pool.wait_closed()
        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Erro: {str(e)[:25]}", text_color="red"))
        
        self.is_running = False
        self.after(0, self.finalize_ui)

    def finalize_ui(self):
        self.btn_start.configure(state="normal"); self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text=f"Finalizado Sessão {self.sessao_atual}", text_color="green")
        self.update_comparativo()

    def start_test_thread(self):
        if self.sessao_atual == 1: self.data_sessao_1 = []
        else: self.data_sessao_2 = []
        self.is_running = True; self.stop_event.clear()
        self.btn_start.configure(state="disabled"); self.btn_stop.configure(state="normal")
        args = (self.entry_query.get("0.0", "end").strip(), self.entry_total.get(), self.entry_concur.get(),
                self.entry_host.get(), self.entry_user.get(), self.entry_pass.get(), self.entry_db.get())
        self.update_plots_live()
        threading.Thread(target=lambda: asyncio.run(self.run_stress_test(*args)), daemon=True).start()

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
