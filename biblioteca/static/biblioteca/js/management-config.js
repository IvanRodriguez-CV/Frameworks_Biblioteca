export const resources = {
  books: {
    label: "libros",
    endpoint: "/api/books/",
    fields: [
      { name: "title", label: "Título", required: true },
      { name: "isbn", label: "ISBN" },
      { name: "author", label: "Autor", type: "select", source: "authors", required: true },
      { name: "category", label: "Categoría", type: "select", source: "categories", required: true },
      { name: "publication_year", label: "Año de publicación", type: "number", min: 1000 },
      { name: "description", label: "Descripción", type: "textarea" },
      { name: "initial_copies", label: "Ejemplares iniciales (1-100)", type: "number", min: 1, max: 100 },
    ],
  },
  authors: {
    label: "autores",
    endpoint: "/api/authors/",
    fields: [
      { name: "name", label: "Nombre", required: true },
      { name: "biography", label: "Biografía", type: "textarea" },
    ],
  },
  categories: {
    label: "categorías",
    endpoint: "/api/categories/",
    fields: [
      { name: "name", label: "Nombre", required: true },
      { name: "description", label: "Descripción", type: "textarea" },
    ],
  },
  copies: {
    label: "ejemplares",
    endpoint: "/api/copies/",
    fields: [{ name: "book", label: "Libro", type: "select", source: "books", required: true }],
    canEdit: false,
  },
  users: {
    label: "usuarios",
    endpoint: "/api/users/",
    fields: [
      { name: "username", label: "Nombre de usuario", required: true },
      { name: "email", label: "Correo electrónico", type: "email", required: true },
      { name: "first_name", label: "Nombre" },
      { name: "last_name", label: "Apellido" },
      {
        name: "role",
        label: "Rol",
        type: "select",
        required: true,
        options: [
          ["reader", "Lector"],
          ["librarian", "Bibliotecario"],
          ["admin", "Administrador"],
        ],
      },
      { name: "is_active", label: "Cuenta activa", type: "checkbox", defaultValue: true },
      { name: "password", label: "Contraseña", type: "password", requiredOnCreate: true },
    ],
  },
  loans: {
    label: "préstamos",
    endpoint: "/api/loans/",
    fields: [
      { name: "copy", label: "Ejemplar", type: "select", source: "copies", required: true },
      { name: "requested_user_id", label: "Usuario", type: "select", source: "users" },
      { name: "due_date", label: "Fecha límite (AAAA-MM-DD)", type: "date" },
    ],
    canEdit: false,
    canDelete: false,
  },
};

export function displayRole(role) {
  return { reader: "Lector", librarian: "Bibliotecario", admin: "Administrador" }[role] || role;
}

export function displayStatus(status) {
  return {
    available: "Disponible",
    loaned: "Prestado",
    maintenance: "Mantenimiento",
    active: "Activo",
    returned: "Devuelto",
  }[status] || status;
}
