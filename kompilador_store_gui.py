#!/usr/bin/env python3
"""
=====================================================================
 KOMPILADOR STORE — Programa de escritorio (Python + Tkinter + SQLite)
=====================================================================
Aplicación de ventana única, sin dependencias externas (todo viene
incluido con Python: tkinter y sqlite3). Al abrirla crea (o reutiliza)
el archivo kompilador_store.db en la misma carpeta donde esté el
programa, así que tus datos quedan guardados entre sesiones.

Módulos: Resumen, Catálogo (categorías/marcas/productos), Locales,
Inventario, Clientes, Ventas y Reportes — con alta y baja (agregar y
eliminar) en cada uno.

Cómo ejecutar:
    python3 kompilador_store_gui.py
(o usa el ejecutable .exe / binario si te generamos uno empaquetado)
=====================================================================
"""

import sqlite3
import sys
import os
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox


# =====================================================================
# UBICACIÓN DE LA BASE DE DATOS (junto al programa, funcione .py o .exe)
# =====================================================================
def ruta_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_PATH = os.path.join(ruta_base(), "kompilador_store.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS locales (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    codigo   TEXT UNIQUE NOT NULL,
    tipo     TEXT NOT NULL DEFAULT 'tienda' CHECK (tipo IN ('tienda','bodega','ecommerce')),
    ciudad   TEXT
);

CREATE TABLE IF NOT EXISTS categorias (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marcas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sku          TEXT UNIQUE NOT NULL,
    nombre       TEXT NOT NULL,
    categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
    marca_id     INTEGER REFERENCES marcas(id) ON DELETE SET NULL,
    precio_venta NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT NOT NULL,
    email    TEXT UNIQUE NOT NULL,
    telefono TEXT
);

CREATE TABLE IF NOT EXISTS inventario (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id            INTEGER NOT NULL REFERENCES locales(id) ON DELETE CASCADE,
    producto_id         INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cantidad_disponible INTEGER NOT NULL DEFAULT 0,
    stock_minimo        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (local_id, producto_id)
);

CREATE TABLE IF NOT EXISTS ventas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_orden TEXT UNIQUE NOT NULL,
    cliente_id   INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    local_id     INTEGER NOT NULL REFERENCES locales(id) ON DELETE CASCADE,
    fecha        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total        NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id        INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    producto_id     INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cantidad        INTEGER NOT NULL,
    precio_unitario NUMERIC NOT NULL,
    subtotal        NUMERIC NOT NULL
);
"""


# =====================================================================
# CAPA DE DATOS (sin nada de Tkinter — se puede probar por separado)
# =====================================================================
class BaseDatos:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ---------- categorías ----------
    def listar_categorias(self):
        return self.conn.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()

    def agregar_categoria(self, nombre):
        self.conn.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        self.conn.commit()

    def eliminar_categoria(self, id_):
        self.conn.execute("DELETE FROM categorias WHERE id=?", (id_,))
        self.conn.commit()

    # ---------- marcas ----------
    def listar_marcas(self):
        return self.conn.execute("SELECT * FROM marcas ORDER BY nombre").fetchall()

    def agregar_marca(self, nombre):
        self.conn.execute("INSERT INTO marcas (nombre) VALUES (?)", (nombre,))
        self.conn.commit()

    def eliminar_marca(self, id_):
        self.conn.execute("DELETE FROM marcas WHERE id=?", (id_,))
        self.conn.commit()

    # ---------- productos ----------
    def listar_productos(self):
        return self.conn.execute("""
            SELECT p.id, p.sku, p.nombre, p.precio_venta,
                   COALESCE(c.nombre,'—') AS categoria, COALESCE(m.nombre,'—') AS marca
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            LEFT JOIN marcas m ON p.marca_id = m.id
            ORDER BY p.nombre
        """).fetchall()

    def agregar_producto(self, sku, nombre, precio, categoria_id=None, marca_id=None):
        self.conn.execute(
            "INSERT INTO productos (sku, nombre, precio_venta, categoria_id, marca_id) VALUES (?,?,?,?,?)",
            (sku, nombre, precio, categoria_id, marca_id),
        )
        self.conn.commit()

    def eliminar_producto(self, id_):
        self.conn.execute("DELETE FROM productos WHERE id=?", (id_,))
        self.conn.commit()

    def tiene_ventas(self, producto_id):
        row = self.conn.execute("SELECT COUNT(*) AS n FROM detalle_venta WHERE producto_id=?",
                                 (producto_id,)).fetchone()
        return row["n"] > 0

    # ---------- locales ----------
    def listar_locales(self):
        return self.conn.execute("SELECT * FROM locales ORDER BY nombre").fetchall()

    def agregar_local(self, nombre, codigo, tipo, ciudad):
        self.conn.execute("INSERT INTO locales (nombre, codigo, tipo, ciudad) VALUES (?,?,?,?)",
                           (nombre, codigo, tipo, ciudad))
        self.conn.commit()

    def eliminar_local(self, id_):
        self.conn.execute("DELETE FROM locales WHERE id=?", (id_,))
        self.conn.commit()

    def local_tiene_datos(self, local_id):
        n_inv = self.conn.execute("SELECT COUNT(*) AS n FROM inventario WHERE local_id=?",
                                   (local_id,)).fetchone()["n"]
        n_ventas = self.conn.execute("SELECT COUNT(*) AS n FROM ventas WHERE local_id=?",
                                      (local_id,)).fetchone()["n"]
        return n_inv > 0 or n_ventas > 0

    # ---------- clientes ----------
    def listar_clientes(self):
        return self.conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()

    def agregar_cliente(self, nombre, email, telefono):
        self.conn.execute("INSERT INTO clientes (nombre, email, telefono) VALUES (?,?,?)",
                           (nombre, email, telefono))
        self.conn.commit()

    def eliminar_cliente(self, id_):
        self.conn.execute("DELETE FROM clientes WHERE id=?", (id_,))
        self.conn.commit()

    # ---------- inventario ----------
    def listar_inventario(self):
        return self.conn.execute("""
            SELECT i.id, l.nombre AS local, p.nombre AS producto,
                   i.cantidad_disponible, i.stock_minimo, i.local_id, i.producto_id
            FROM inventario i
            JOIN locales l ON i.local_id = l.id
            JOIN productos p ON i.producto_id = p.id
            ORDER BY l.nombre, p.nombre
        """).fetchall()

    def cargar_stock(self, local_id, producto_id, cantidad, stock_minimo):
        existente = self.conn.execute(
            "SELECT id FROM inventario WHERE local_id=? AND producto_id=?", (local_id, producto_id)
        ).fetchone()
        if existente:
            self.conn.execute(
                "UPDATE inventario SET cantidad_disponible = cantidad_disponible + ?, stock_minimo=? WHERE id=?",
                (cantidad, stock_minimo, existente["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO inventario (local_id, producto_id, cantidad_disponible, stock_minimo) VALUES (?,?,?,?)",
                (local_id, producto_id, cantidad, stock_minimo),
            )
        self.conn.commit()

    def eliminar_inventario(self, id_):
        self.conn.execute("DELETE FROM inventario WHERE id=?", (id_,))
        self.conn.commit()

    def stock_disponible(self, local_id, producto_id):
        row = self.conn.execute(
            "SELECT cantidad_disponible FROM inventario WHERE local_id=? AND producto_id=?",
            (local_id, producto_id),
        ).fetchone()
        return row["cantidad_disponible"] if row else 0

    def stock_bajo(self):
        return self.conn.execute("""
            SELECT l.nombre AS local, p.nombre AS producto, i.cantidad_disponible, i.stock_minimo
            FROM inventario i
            JOIN locales l ON i.local_id = l.id
            JOIN productos p ON i.producto_id = p.id
            WHERE i.cantidad_disponible <= i.stock_minimo
        """).fetchall()

    # ---------- ventas ----------
    def listar_ventas(self):
        return self.conn.execute("""
            SELECT v.id, v.numero_orden, v.fecha, v.total, l.nombre AS local,
                   COALESCE(c.nombre,'—') AS cliente
            FROM ventas v
            JOIN locales l ON v.local_id = l.id
            LEFT JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.id DESC
        """).fetchall()

    def crear_venta(self, local_id, cliente_id, items):
        """items: lista de dicts {producto_id, cantidad, precio_unitario}"""
        for it in items:
            disponible = self.stock_disponible(local_id, it["producto_id"])
            if disponible < it["cantidad"]:
                raise ValueError(f"Stock insuficiente (disponible: {disponible})")

        total = sum(it["cantidad"] * it["precio_unitario"] for it in items)
        numero_orden = "ORD-" + datetime.now().strftime("%Y%m%d%H%M%S")
        cur = self.conn.execute(
            "INSERT INTO ventas (numero_orden, cliente_id, local_id, total) VALUES (?,?,?,?)",
            (numero_orden, cliente_id, local_id, total),
        )
        venta_id = cur.lastrowid
        for it in items:
            subtotal = it["cantidad"] * it["precio_unitario"]
            self.conn.execute(
                "INSERT INTO detalle_venta (venta_id, producto_id, cantidad, precio_unitario, subtotal) "
                "VALUES (?,?,?,?,?)",
                (venta_id, it["producto_id"], it["cantidad"], it["precio_unitario"], subtotal),
            )
            self.conn.execute(
                "UPDATE inventario SET cantidad_disponible = cantidad_disponible - ? "
                "WHERE local_id=? AND producto_id=?",
                (it["cantidad"], local_id, it["producto_id"]),
            )
        self.conn.commit()
        return venta_id, numero_orden

    def eliminar_venta(self, venta_id):
        """Elimina la venta y repone el inventario descontado."""
        items = self.conn.execute(
            "SELECT * FROM detalle_venta WHERE venta_id=?", (venta_id,)
        ).fetchall()
        venta = self.conn.execute("SELECT * FROM ventas WHERE id=?", (venta_id,)).fetchone()
        for it in items:
            self.conn.execute(
                "UPDATE inventario SET cantidad_disponible = cantidad_disponible + ? "
                "WHERE local_id=? AND producto_id=?",
                (it["cantidad"], venta["local_id"], it["producto_id"]),
            )
        self.conn.execute("DELETE FROM ventas WHERE id=?", (venta_id,))
        self.conn.commit()

    def detalle_de_venta(self, venta_id):
        return self.conn.execute("""
            SELECT dv.cantidad, dv.precio_unitario, dv.subtotal, p.nombre AS producto
            FROM detalle_venta dv JOIN productos p ON dv.producto_id = p.id
            WHERE dv.venta_id=?
        """, (venta_id,)).fetchall()

    # ---------- reportes ----------
    def productos_mas_vendidos(self, limite=8):
        return self.conn.execute("""
            SELECT p.nombre, SUM(dv.cantidad) AS unidades
            FROM detalle_venta dv JOIN productos p ON dv.producto_id = p.id
            GROUP BY p.id ORDER BY unidades DESC LIMIT ?
        """, (limite,)).fetchall()

    def ventas_por_local(self):
        return self.conn.execute("""
            SELECT l.nombre AS local, COUNT(v.id) AS num_ventas, COALESCE(SUM(v.total),0) AS total
            FROM locales l LEFT JOIN ventas v ON v.local_id = l.id
            GROUP BY l.id ORDER BY total DESC
        """).fetchall()

    def resumen(self):
        n_prod = self.conn.execute("SELECT COUNT(*) AS n FROM productos").fetchone()["n"]
        n_loc = self.conn.execute("SELECT COUNT(*) AS n FROM locales").fetchone()["n"]
        n_cli = self.conn.execute("SELECT COUNT(*) AS n FROM clientes").fetchone()["n"]
        total_vendido = self.conn.execute("SELECT COALESCE(SUM(total),0) AS t FROM ventas").fetchone()["t"]
        return n_prod, n_loc, n_cli, total_vendido


def money(n):
    return "$" + f"{n:,.0f}".replace(",", ".")


# =====================================================================
# DATOS DE EJEMPLO (solo si la base de datos está vacía)
# =====================================================================
def poblar_si_vacio(db: BaseDatos):
    if db.listar_productos():
        return
    db.agregar_categoria("Periféricos")
    db.agregar_marca("Kompilador Hardware")
    cat_id = db.listar_categorias()[0]["id"]
    marca_id = db.listar_marcas()[0]["id"]
    db.agregar_producto("KOMP-KB-001", "Teclado mecánico Kompilador 65%", 320000, cat_id, marca_id)
    db.agregar_producto("KOMP-MS-001", "Mouse inalámbrico Kompilador Lite", 95000, cat_id, marca_id)
    db.agregar_local("Kompilador Store - Medellín", "MED-01", "tienda", "Medellín")
    db.agregar_local("Kompilador Store - Online", "ONL-01", "ecommerce", "—")

    locales = db.listar_locales()
    productos = db.listar_productos()
    medellin = next(l for l in locales if l["codigo"] == "MED-01")
    teclado = next(p for p in productos if p["sku"] == "KOMP-KB-001")
    mouse = next(p for p in productos if p["sku"] == "KOMP-MS-001")
    db.cargar_stock(medellin["id"], teclado["id"], 15, 3)
    db.cargar_stock(medellin["id"], mouse["id"], 30, 5)
    db.agregar_cliente("Carlos Gómez", "carlos@example.com", "3001234567")


# =====================================================================
# INTERFAZ GRÁFICA
# =====================================================================
COLOR_BG = "#EFEBE3"
COLOR_SURFACE = "#FFFDF8"
COLOR_INDIGO = "#2E3A59"
COLOR_RUST = "#B1442E"
FONT_TITLE = ("Georgia", 16, "bold")
FONT_LABEL = ("Segoe UI", 10)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kompilador Store — Panel de gestión")
        self.geometry("1080x680")
        self.configure(bg=COLOR_BG)
        self.db = BaseDatos()
        poblar_si_vacio(self.db)
        self.venta_items = []  # líneas de la venta en construcción

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook.Tab", padding=(14, 8), font=FONT_LABEL)
        style.configure("Treeview", rowheight=24, font=FONT_LABEL)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background=COLOR_INDIGO, foreground="white")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_resumen = ttk.Frame(notebook)
        self.tab_catalogo = ttk.Frame(notebook)
        self.tab_locales = ttk.Frame(notebook)
        self.tab_inventario = ttk.Frame(notebook)
        self.tab_clientes = ttk.Frame(notebook)
        self.tab_ventas = ttk.Frame(notebook)
        self.tab_reportes = ttk.Frame(notebook)

        for frame, texto in [
            (self.tab_resumen, "Resumen"), (self.tab_catalogo, "Catálogo"),
            (self.tab_locales, "Locales"), (self.tab_inventario, "Inventario"),
            (self.tab_clientes, "Clientes"), (self.tab_ventas, "Ventas"),
            (self.tab_reportes, "Reportes"),
        ]:
            notebook.add(frame, text=texto)

        self._armar_resumen(self.tab_resumen)
        self._armar_catalogo(self.tab_catalogo)
        self._armar_locales(self.tab_locales)
        self._armar_inventario(self.tab_inventario)
        self._armar_clientes(self.tab_clientes)
        self._armar_ventas(self.tab_ventas)
        self._armar_reportes(self.tab_reportes)

        self.refrescar_todo()

    # -----------------------------------------------------------------
    def refrescar_todo(self):
        self._refrescar_resumen()
        self._refrescar_categorias()
        self._refrescar_marcas()
        self._refrescar_productos()
        self._refrescar_locales()
        self._refrescar_inventario()
        self._refrescar_clientes()
        self._refrescar_combos_venta()
        self._refrescar_ventas()
        self._refrescar_reportes()

    # =================== RESUMEN ===================
    def _armar_resumen(self, parent):
        self.lbl_stats = tk.Label(parent, text="", font=FONT_TITLE, bg=COLOR_BG, justify="left", anchor="w")
        self.lbl_stats.pack(fill="x", padx=16, pady=16)
        ttk.Button(parent, text="Actualizar", command=self.refrescar_todo).pack(anchor="w", padx=16)

        tk.Label(parent, text="Stock por debajo del mínimo", font=("Segoe UI", 11, "bold"), bg=COLOR_BG)\
            .pack(anchor="w", padx=16, pady=(18, 4))
        self.tree_resumen_stock = self._crear_tabla(parent, ["Local", "Producto", "Disponible", "Mínimo"])

    def _refrescar_resumen(self):
        n_prod, n_loc, n_cli, total = self.db.resumen()
        self.lbl_stats.config(
            text=f"Productos: {n_prod}    Locales: {n_loc}    Clientes: {n_cli}    "
                 f"Vendido en total: {money(total)}"
        )
        self._llenar_tabla(self.tree_resumen_stock, [
            (r["local"], r["producto"], r["cantidad_disponible"], r["stock_minimo"])
            for r in self.db.stock_bajo()
        ])

    # =================== CATÁLOGO ===================
    def _armar_catalogo(self, parent):
        sub = ttk.Notebook(parent)
        sub.pack(fill="both", expand=True, padx=8, pady=8)

        # -- categorías --
        f_cat = ttk.Frame(sub)
        sub.add(f_cat, text="Categorías")
        form = ttk.Frame(f_cat); form.pack(fill="x", padx=10, pady=10)
        self.e_cat_nombre = self._campo(form, "Nombre:")
        ttk.Button(form, text="Agregar", command=self._agregar_categoria).pack(side="left", padx=4)
        self.tree_categorias = self._crear_tabla(f_cat, ["ID", "Nombre"])
        ttk.Button(f_cat, text="Eliminar seleccionada", command=self._eliminar_categoria).pack(anchor="w", padx=10, pady=6)

        # -- marcas --
        f_marca = ttk.Frame(sub)
        sub.add(f_marca, text="Marcas")
        form = ttk.Frame(f_marca); form.pack(fill="x", padx=10, pady=10)
        self.e_marca_nombre = self._campo(form, "Nombre:")
        ttk.Button(form, text="Agregar", command=self._agregar_marca).pack(side="left", padx=4)
        self.tree_marcas = self._crear_tabla(f_marca, ["ID", "Nombre"])
        ttk.Button(f_marca, text="Eliminar seleccionada", command=self._eliminar_marca).pack(anchor="w", padx=10, pady=6)

        # -- productos --
        f_prod = ttk.Frame(sub)
        sub.add(f_prod, text="Productos")
        form = ttk.Frame(f_prod); form.pack(fill="x", padx=10, pady=10)
        self.e_prod_sku = self._campo(form, "SKU:", width=10)
        self.e_prod_nombre = self._campo(form, "Nombre:", width=22)
        self.cb_prod_categoria = self._combo(form, "Categoría:")
        self.cb_prod_marca = self._combo(form, "Marca:")
        self.e_prod_precio = self._campo(form, "Precio:", width=10)
        ttk.Button(form, text="Agregar", command=self._agregar_producto).pack(side="left", padx=4)
        self.tree_productos = self._crear_tabla(
            f_prod, ["ID", "SKU", "Nombre", "Categoría", "Marca", "Precio"])
        ttk.Button(f_prod, text="Eliminar seleccionado", command=self._eliminar_producto).pack(anchor="w", padx=10, pady=6)

    def _agregar_categoria(self):
        nombre = self.e_cat_nombre.get().strip()
        if not nombre:
            return messagebox.showwarning("Falta información", "Escribe un nombre.")
        self.db.agregar_categoria(nombre)
        self.e_cat_nombre.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_categoria(self):
        id_ = self._id_seleccionado(self.tree_categorias)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona una categoría de la lista.")
        if messagebox.askyesno("Confirmar", "¿Eliminar esta categoría? Los productos que la usan quedarán sin categoría."):
            self.db.eliminar_categoria(id_)
            self.refrescar_todo()

    def _agregar_marca(self):
        nombre = self.e_marca_nombre.get().strip()
        if not nombre:
            return messagebox.showwarning("Falta información", "Escribe un nombre.")
        self.db.agregar_marca(nombre)
        self.e_marca_nombre.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_marca(self):
        id_ = self._id_seleccionado(self.tree_marcas)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona una marca de la lista.")
        if messagebox.askyesno("Confirmar", "¿Eliminar esta marca? Los productos que la usan quedarán sin marca."):
            self.db.eliminar_marca(id_)
            self.refrescar_todo()

    def _agregar_producto(self):
        sku = self.e_prod_sku.get().strip()
        nombre = self.e_prod_nombre.get().strip()
        precio_txt = self.e_prod_precio.get().strip()
        if not sku or not nombre or not precio_txt:
            return messagebox.showwarning("Falta información", "Completa SKU, nombre y precio.")
        try:
            precio = float(precio_txt)
        except ValueError:
            return messagebox.showwarning("Precio inválido", "El precio debe ser un número.")
        cat_id = self._valor_combo(self.cb_prod_categoria)
        marca_id = self._valor_combo(self.cb_prod_marca)
        try:
            self.db.agregar_producto(sku, nombre, precio, cat_id, marca_id)
        except sqlite3.IntegrityError:
            return messagebox.showerror("SKU repetido", "Ya existe un producto con ese SKU.")
        for e in (self.e_prod_sku, self.e_prod_nombre, self.e_prod_precio):
            e.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_producto(self):
        id_ = self._id_seleccionado(self.tree_productos)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona un producto de la lista.")
        aviso = ""
        if self.db.tiene_ventas(id_):
            aviso = "\n\nEste producto tiene ventas registradas: también se borrará ese historial."
        if messagebox.askyesno("Confirmar", "¿Eliminar este producto? También se borrará su inventario." + aviso):
            self.db.eliminar_producto(id_)
            self.refrescar_todo()

    def _refrescar_categorias(self):
        self._llenar_tabla(self.tree_categorias, [(c["id"], c["nombre"]) for c in self.db.listar_categorias()])

    def _refrescar_marcas(self):
        self._llenar_tabla(self.tree_marcas, [(m["id"], m["nombre"]) for m in self.db.listar_marcas()])

    def _refrescar_productos(self):
        self._llenar_tabla(self.tree_productos, [
            (p["id"], p["sku"], p["nombre"], p["categoria"], p["marca"], money(p["precio_venta"]))
            for p in self.db.listar_productos()
        ])
        self._llenar_combo(self.cb_prod_categoria, self.db.listar_categorias())
        self._llenar_combo(self.cb_prod_marca, self.db.listar_marcas())

    # =================== LOCALES ===================
    def _armar_locales(self, parent):
        form = ttk.Frame(parent); form.pack(fill="x", padx=10, pady=10)
        self.e_local_nombre = self._campo(form, "Nombre:", width=20)
        self.e_local_codigo = self._campo(form, "Código:", width=10)
        self.cb_local_tipo = ttk.Combobox(form, values=["tienda", "bodega", "ecommerce"], width=10, state="readonly")
        self.cb_local_tipo.set("tienda")
        tk.Label(form, text="Tipo:", bg=COLOR_BG).pack(side="left", padx=(8, 2))
        self.cb_local_tipo.pack(side="left", padx=4)
        self.e_local_ciudad = self._campo(form, "Ciudad:", width=14)
        ttk.Button(form, text="Agregar", command=self._agregar_local).pack(side="left", padx=6)

        self.tree_locales = self._crear_tabla(parent, ["ID", "Nombre", "Código", "Tipo", "Ciudad"])
        ttk.Button(parent, text="Eliminar seleccionado", command=self._eliminar_local).pack(anchor="w", padx=10, pady=6)

    def _agregar_local(self):
        nombre = self.e_local_nombre.get().strip()
        codigo = self.e_local_codigo.get().strip()
        tipo = self.cb_local_tipo.get()
        ciudad = self.e_local_ciudad.get().strip() or "—"
        if not nombre or not codigo:
            return messagebox.showwarning("Falta información", "Completa nombre y código.")
        try:
            self.db.agregar_local(nombre, codigo, tipo, ciudad)
        except sqlite3.IntegrityError:
            return messagebox.showerror("Código repetido", "Ya existe un local con ese código.")
        for e in (self.e_local_nombre, self.e_local_codigo, self.e_local_ciudad):
            e.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_local(self):
        id_ = self._id_seleccionado(self.tree_locales)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona un local de la lista.")
        aviso = ""
        if self.db.local_tiene_datos(id_):
            aviso = "\n\nEste local tiene inventario y/o ventas: también se eliminarán."
        if messagebox.askyesno("Confirmar", "¿Eliminar este local?" + aviso):
            self.db.eliminar_local(id_)
            self.refrescar_todo()

    def _refrescar_locales(self):
        self._llenar_tabla(self.tree_locales, [
            (l["id"], l["nombre"], l["codigo"], l["tipo"], l["ciudad"]) for l in self.db.listar_locales()
        ])

    # =================== INVENTARIO ===================
    def _armar_inventario(self, parent):
        form = ttk.Frame(parent); form.pack(fill="x", padx=10, pady=10)
        self.cb_inv_local = self._combo(form, "Local:")
        self.cb_inv_producto = self._combo(form, "Producto:")
        self.e_inv_cantidad = self._campo(form, "Cantidad a sumar:", width=8)
        self.e_inv_minimo = self._campo(form, "Stock mínimo:", width=8)
        ttk.Button(form, text="Cargar stock", command=self._cargar_stock).pack(side="left", padx=6)

        self.tree_inventario = self._crear_tabla(parent, ["ID", "Local", "Producto", "Disponible", "Mínimo"])
        ttk.Button(parent, text="Eliminar registro seleccionado", command=self._eliminar_inventario)\
            .pack(anchor="w", padx=10, pady=6)

    def _cargar_stock(self):
        local_id = self._valor_combo(self.cb_inv_local)
        producto_id = self._valor_combo(self.cb_inv_producto)
        cantidad_txt = self.e_inv_cantidad.get().strip()
        minimo_txt = self.e_inv_minimo.get().strip() or "0"
        if not local_id or not producto_id or not cantidad_txt:
            return messagebox.showwarning("Falta información", "Elige local, producto y cantidad.")
        try:
            cantidad = int(cantidad_txt)
            minimo = int(minimo_txt)
        except ValueError:
            return messagebox.showwarning("Valor inválido", "Cantidad y mínimo deben ser números enteros.")
        self.db.cargar_stock(local_id, producto_id, cantidad, minimo)
        self.e_inv_cantidad.delete(0, tk.END)
        self.e_inv_minimo.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_inventario(self):
        id_ = self._id_seleccionado(self.tree_inventario)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona un registro de inventario.")
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro de inventario?"):
            self.db.eliminar_inventario(id_)
            self.refrescar_todo()

    def _refrescar_inventario(self):
        self._llenar_tabla(self.tree_inventario, [
            (i["id"], i["local"], i["producto"], i["cantidad_disponible"], i["stock_minimo"])
            for i in self.db.listar_inventario()
        ])
        self._llenar_combo(self.cb_inv_local, self.db.listar_locales())
        self._llenar_combo(self.cb_inv_producto, self.db.listar_productos())

    # =================== CLIENTES ===================
    def _armar_clientes(self, parent):
        form = ttk.Frame(parent); form.pack(fill="x", padx=10, pady=10)
        self.e_cli_nombre = self._campo(form, "Nombre:", width=18)
        self.e_cli_email = self._campo(form, "Email:", width=20)
        self.e_cli_telefono = self._campo(form, "Teléfono:", width=14)
        ttk.Button(form, text="Agregar", command=self._agregar_cliente).pack(side="left", padx=6)

        self.tree_clientes = self._crear_tabla(parent, ["ID", "Nombre", "Email", "Teléfono"])
        ttk.Button(parent, text="Eliminar seleccionado", command=self._eliminar_cliente).pack(anchor="w", padx=10, pady=6)

    def _agregar_cliente(self):
        nombre = self.e_cli_nombre.get().strip()
        email = self.e_cli_email.get().strip()
        telefono = self.e_cli_telefono.get().strip()
        if not nombre or not email:
            return messagebox.showwarning("Falta información", "Completa nombre y email.")
        try:
            self.db.agregar_cliente(nombre, email, telefono)
        except sqlite3.IntegrityError:
            return messagebox.showerror("Email repetido", "Ya existe un cliente con ese email.")
        for e in (self.e_cli_nombre, self.e_cli_email, self.e_cli_telefono):
            e.delete(0, tk.END)
        self.refrescar_todo()

    def _eliminar_cliente(self):
        id_ = self._id_seleccionado(self.tree_clientes)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona un cliente de la lista.")
        if messagebox.askyesno("Confirmar", "¿Eliminar este cliente? Sus ventas anteriores se conservan sin cliente asociado."):
            self.db.eliminar_cliente(id_)
            self.refrescar_todo()

    def _refrescar_clientes(self):
        self._llenar_tabla(self.tree_clientes, [
            (c["id"], c["nombre"], c["email"], c["telefono"] or "—") for c in self.db.listar_clientes()
        ])

    # =================== VENTAS ===================
    def _armar_ventas(self, parent):
        form = ttk.Frame(parent); form.pack(fill="x", padx=10, pady=10)
        self.cb_venta_local = self._combo(form, "Local:")
        self.cb_venta_cliente = self._combo(form, "Cliente:", opcional=True)

        form2 = ttk.Frame(parent); form2.pack(fill="x", padx=10)
        self.cb_venta_producto = self._combo(form2, "Producto:")
        self.e_venta_cantidad = self._campo(form2, "Cantidad:", width=6)
        ttk.Button(form2, text="+ Agregar línea", command=self._agregar_linea_venta).pack(side="left", padx=6)

        self.tree_lineas = self._crear_tabla(parent, ["Producto", "Cantidad", "Precio", "Subtotal"], alto=4)
        fila_total = ttk.Frame(parent); fila_total.pack(fill="x", padx=10, pady=4)
        self.lbl_total_venta = tk.Label(fila_total, text="Total: $0", font=("Segoe UI", 11, "bold"), bg=COLOR_BG)
        self.lbl_total_venta.pack(side="left")
        ttk.Button(fila_total, text="Quitar línea seleccionada", command=self._quitar_linea_venta)\
            .pack(side="left", padx=10)
        ttk.Button(fila_total, text="Registrar venta", command=self._registrar_venta).pack(side="right")

        tk.Label(parent, text="Historial de ventas", font=("Segoe UI", 11, "bold"), bg=COLOR_BG)\
            .pack(anchor="w", padx=10, pady=(14, 4))
        self.tree_ventas = self._crear_tabla(parent, ["ID", "Orden", "Fecha", "Local", "Cliente", "Total"])
        ttk.Button(parent, text="Eliminar venta seleccionada (repone stock)", command=self._eliminar_venta)\
            .pack(anchor="w", padx=10, pady=6)

    def _agregar_linea_venta(self):
        producto_id = self._valor_combo(self.cb_venta_producto)
        cantidad_txt = self.e_venta_cantidad.get().strip()
        if not producto_id or not cantidad_txt:
            return messagebox.showwarning("Falta información", "Elige un producto y una cantidad.")
        try:
            cantidad = int(cantidad_txt)
        except ValueError:
            return messagebox.showwarning("Cantidad inválida", "La cantidad debe ser un número entero.")
        producto = next(p for p in self.db.listar_productos() if p["id"] == producto_id)
        for it in self.venta_items:
            if it["producto_id"] == producto_id:
                it["cantidad"] += cantidad
                break
        else:
            self.venta_items.append({
                "producto_id": producto_id, "nombre": producto["nombre"],
                "cantidad": cantidad, "precio_unitario": producto["precio_venta"],
            })
        self.e_venta_cantidad.delete(0, tk.END)
        self._refrescar_lineas_venta()

    def _quitar_linea_venta(self):
        sel = self.tree_lineas.selection()
        if not sel:
            return
        idx = self.tree_lineas.index(sel[0])
        del self.venta_items[idx]
        self._refrescar_lineas_venta()

    def _refrescar_lineas_venta(self):
        total = sum(it["cantidad"] * it["precio_unitario"] for it in self.venta_items)
        self._llenar_tabla(self.tree_lineas, [
            (it["nombre"], it["cantidad"], money(it["precio_unitario"]), money(it["cantidad"] * it["precio_unitario"]))
            for it in self.venta_items
        ])
        self.lbl_total_venta.config(text=f"Total: {money(total)}")

    def _registrar_venta(self):
        local_id = self._valor_combo(self.cb_venta_local)
        cliente_id = self._valor_combo(self.cb_venta_cliente)
        if not local_id:
            return messagebox.showwarning("Falta información", "Elige el local donde se realiza la venta.")
        if not self.venta_items:
            return messagebox.showwarning("Falta información", "Agrega al menos una línea de producto.")
        try:
            self.db.crear_venta(local_id, cliente_id, self.venta_items)
        except ValueError as e:
            return messagebox.showerror("Stock insuficiente", str(e))
        self.venta_items = []
        self._refrescar_lineas_venta()
        self.refrescar_todo()
        messagebox.showinfo("Listo", "Venta registrada correctamente.")

    def _eliminar_venta(self):
        id_ = self._id_seleccionado(self.tree_ventas)
        if id_ is None:
            return messagebox.showinfo("Elige una fila", "Selecciona una venta de la lista.")
        if messagebox.askyesno("Confirmar", "¿Eliminar esta venta? El inventario vendido se repondrá."):
            self.db.eliminar_venta(id_)
            self.refrescar_todo()

    def _refrescar_combos_venta(self):
        self._llenar_combo(self.cb_venta_local, self.db.listar_locales())
        self._llenar_combo(self.cb_venta_cliente, self.db.listar_clientes(), opcional=True)
        self._llenar_combo(self.cb_venta_producto, self.db.listar_productos())

    def _refrescar_ventas(self):
        self._llenar_tabla(self.tree_ventas, [
            (v["id"], v["numero_orden"], v["fecha"], v["local"], v["cliente"], money(v["total"]))
            for v in self.db.listar_ventas()
        ])

    # =================== REPORTES ===================
    def _armar_reportes(self, parent):
        ttk.Button(parent, text="Actualizar reportes", command=self.refrescar_todo).pack(anchor="w", padx=10, pady=10)
        tk.Label(parent, text="Productos más vendidos", font=("Segoe UI", 11, "bold"), bg=COLOR_BG)\
            .pack(anchor="w", padx=10)
        self.tree_top_productos = self._crear_tabla(parent, ["Producto", "Unidades vendidas"], alto=6)

        tk.Label(parent, text="Ventas por local", font=("Segoe UI", 11, "bold"), bg=COLOR_BG)\
            .pack(anchor="w", padx=10, pady=(14, 4))
        self.tree_ventas_local = self._crear_tabla(parent, ["Local", "# Ventas", "Total vendido"], alto=6)

    def _refrescar_reportes(self):
        self._llenar_tabla(self.tree_top_productos, [
            (r["nombre"], r["unidades"]) for r in self.db.productos_mas_vendidos()
        ])
        self._llenar_tabla(self.tree_ventas_local, [
            (r["local"], r["num_ventas"], money(r["total"])) for r in self.db.ventas_por_local()
        ])

    # =====================================================================
    # WIDGETS AUXILIARES
    # =====================================================================
    def _campo(self, parent, etiqueta, width=16):
        tk.Label(parent, text=etiqueta, bg=COLOR_BG).pack(side="left", padx=(8, 2))
        entry = ttk.Entry(parent, width=width)
        entry.pack(side="left", padx=2)
        return entry

    def _combo(self, parent, etiqueta, opcional=False):
        tk.Label(parent, text=etiqueta, bg=COLOR_BG).pack(side="left", padx=(8, 2))
        combo = ttk.Combobox(parent, width=24, state="readonly")
        combo.pack(side="left", padx=2)
        combo._opcional = opcional
        return combo

    def _llenar_combo(self, combo, registros, opcional=False):
        etiqueta = lambda r: r["nombre"] if "nombre" in r.keys() else str(dict(r))
        valores = (["— Ninguno —"] if (opcional or getattr(combo, "_opcional", False)) else []) + \
                  [etiqueta(r) for r in registros]
        combo["values"] = valores
        combo._ids = [None] * (1 if (opcional or getattr(combo, "_opcional", False)) else 0) + [r["id"] for r in registros]
        if valores and not combo.get():
            combo.current(0)
        elif not valores:
            combo.set("")

    def _valor_combo(self, combo):
        idx = combo.current()
        if idx is None or idx < 0 or not hasattr(combo, "_ids") or idx >= len(combo._ids):
            return None
        return combo._ids[idx]

    def _crear_tabla(self, parent, columnas, alto=8):
        cont = ttk.Frame(parent)
        cont.pack(fill="both", expand=True, padx=10, pady=6)
        tree = ttk.Treeview(cont, columns=columnas, show="headings", height=alto)
        for c in columnas:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor="w")
        scroll = ttk.Scrollbar(cont, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _llenar_tabla(self, tree, filas):
        tree.delete(*tree.get_children())
        for fila in filas:
            tree.insert("", "end", iid=str(fila[0]) if isinstance(fila[0], int) else None, values=fila)

    def _id_seleccionado(self, tree):
        sel = tree.selection()
        if not sel:
            return None
        return int(sel[0])


if __name__ == "__main__":
    app = App()
    app.mainloop()
