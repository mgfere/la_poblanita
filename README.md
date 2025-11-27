# La Poblanita

La aplicación web trata de resolver los robos hormiga de la carnicería y molino La Poblanita, debido a varias incidencias que ha tenido con la mercancía del negocio. Este sistema soluciona esta problemática por su excelente manejo de inventario y control de salidas de dicha mercancía, además de tener un excelente diseño y seguridad para el local.


![Logo](src/static/images/logo_la_poblanita.png)

## Desarrolladores

- [Miguel Aguilar Feregrino](https://github.com/mgfere)
- [Kristian David Beltran Alarcon](https://github.com/kristian293847)
- [Carlos Antonio Tolentino Estudillo](https://github.com/cqarlod)


## Instalación

Antes de ejecutar este proyecto se necesita tener instalado python3 en adelante y el editor de VS Code.

- **Paso 1:** Lo primero es abrir VS Code desde la carpeta del proyecto **"la_poblanita"**

- **Paso 2:** Una vez abierto el proyecto, se debe crear un entorno virtual y activarlo. Para esto, se abre una nueva terminal en la raíz del proyecto y se escriben los siguientes comandos:

```bash
  python -m venv env
  env/Scripts/activate
```

- **Paso 3:** Después de activar el entorno virtual, se ejecuta el archivo **"requirements.py"** que se encuentra dentro de la carpeta **"src"** y contiene las dependencias necesarias para el proyecto.

```bash
  pip install -r src/requirements.txt
```

**NOTA IMPORTANTE:**

La cadena de conexión está enlazada a la base de datos de producción de Supabase, creada desde la cuenta de los desarrolladores, y no es necesario crear otra base de datos para el uso del proyecto. Sin embargo, esto está mal, por eso se agregó un archivo llamado **"create_db.py"** el cual se encarga de exportar el modelo de la base de datos que se encuentra en **"models.py"** y, seguido, crear toda la base de datos con las tablas y relaciones para el sistema.

- **Paso 4:** Hay que tener en cuenta que para poder ejecutar esto se necesita una cuenta en Supabase y crear un proyecto.

![App Screenshot](https://framerusercontent.com/images/DYdAKBu2c6C5Chjfz1xHF52Q9s.png?width=2672&height=1848)

- **Paso 5:** Antes de crearlo, se copia la contraseña de la base de datos y se guarda de momento. Después de crear el proyecto, se da clic dentro de este y en la parte superior hay una sección llamada **"Connect"**.

  Esta sección contiene la cadena de conexión de la base de datos que estás creando. Esas claves de acceso van en un archivo llamado **".env"** el cual debes crear en la raíz del proyecto con ese mismo nombre.

  Este archivo lo que hace es cargar las claves de tu base de datos dentro de otro archivo llamado **"init.py"** con el fin de que no sean visibles para el público.

  En la siguiente imagen se muestra un ejemplo de dónde se encuentran las claves.

![App Screenshot](https://docs.getwren.ai/assets/images/supabase_2-ad25d5fa5b6a1d32baa39dec27b59905.png)

- **Paso 6:** Ahora, ya que tienes las claves de tu base de datos y el archivo **".env"**, vas a copiar el siguiente código dentro del archivo:

```bash
  DB_USER = postgres.strstsezzdxjcatbkfyt
  DB_PASSWORD = I74eurNyM7EiICj4
  DB_HOST = aws-1-us-east-1.pooler.supabase.com
  DB_PORT = 6543
  DB_NAME = postgres
```

- **Paso 7:** Ya con el código en el archivo, vas a reemplazar las claves que están por las que tienes en tu cadena de conexión. Recuerda que en la imagen anterior se muestra dónde están ubicadas.

- **Paso 8:** Ahora vas a abrir una nueva terminal en la raíz del proyecto y vas a ejecutar el archivo **"create_db.py".** Este archivo crea la base de datos con todas sus tablas y relaciones dentro de Supabase, por lo que ya no es necesario un archivo **".sql"**.

  para ejecutar el archivo ingresa el siguiente comando en la terminal:

```bash
  python -m src/database.create_db
```

- **Paso 9**: Listo, ya tienes el proyecto para poder usarlo en local. Finalmente, vas a ejecutar el último comando en una nueva terminal para poder ejecutar la aplicación y poder usarla correctamente. El comando es el siguiente:

```bash
  python src/app.py
```

- **Paso 10:** Por último, verás un link en la terminal en el que, si das clic, te llevará al navegador donde estará ya lista la aplicación en funcionamiento en local.
