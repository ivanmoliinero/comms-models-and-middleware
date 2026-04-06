# comms-models-and-middleware
To create the VPCs, EC2 instances and dependencies, run inside aws-config:
```
terraform init
terraform plan
terraform apply
```

ATTENTION: The keys and tokens from the session lab (available in AWS Details) must be exported into terminal variables.
```
# These are temporary credentials valid only for the current lab session.
# Copy and paste the entire block provided in the AWS Details panel.
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCY..."
export AWS_SESSION_TOKEN="IQoJb3JpZ2luX2VjEJH//////////wEaCXVzLW..."
```

### IMPORTANT
Add terraform.tfvars to include Grafana Cloud variables securely.
You need to indicate the Prometheus write endpoint, the Grafana user_id and the Grafana API_KEY token.

### GRAFANA CLOUD CONFIG
Aquí tienes los pasos exactos y objetivos para obtener las credenciales y configurar la visualización:
1. Obtener la URL y el Username (Portal de Grafana Cloud)

Estas son las coordenadas a las que tu EC2 enviará el tráfico.

    Inicia sesión en tu cuenta en grafana.com y accede al Cloud Portal.

    Verás tu pila de servicios (Stack). Busca la tarjeta que dice Prometheus y haz clic en Details.

    En esa pantalla, busca la sección Password / API Token.

    Justo encima, verás la Remote Write Endpoint URL (cópiala entera para tu variable) y el Username / Instance ID (un número de 6 o 7 cifras).

2. Generar el Password / API Key (Access Policies)

Grafana ya no permite usar contraseñas simples por seguridad. Tienes que crear un token con permisos específicos de escritura.

    En la misma pantalla de detalles de Prometheus, haz clic en Generate now en la sección de contraseñas, o navega en el menú lateral a Security -> Access Policies.

    Haz clic en Create access policy.

    Ponle un nombre identificativo (ej. aws-ec2-metrics).

    En el apartado de Scopes, debes seleccionar estrictamente metrics:write. No necesitas darle permisos de lectura ni de administración.

    Haz clic en Create y luego en Create token.

    Copia el token alfanumérico largo que aparece en pantalla. Ese es tu grafana_api_key. No podrás volver a verlo una vez cierres la ventana.

3. Verificar la llegada de datos (Grafana UI)

Una vez hayas puesto esas tres variables en tu terraform.tfvars, aplicado el despliegue y esperado un par de minutos, tienes que comprobar que los datos entran.

    Abre tu instancia de Grafana (el enlace que suele ser tu-nombre.grafana.net).

    En el menú lateral izquierdo, ve a Explore.

    En el desplegable superior izquierdo, asegúrate de que está seleccionado tu origen de datos de grafanacloud-prom.

    En la caja de consultas (Query), escribe la métrica up y dale a ejecutar.

    Deberías ver una lista con las IPs locales de tus instancias devolviendo el valor 1 (que significa que están vivas).

4. Importar los Paneles Visuales

No necesitas crear los gráficos desde cero. Puedes descargar las plantillas oficiales que interpretan automáticamente estas métricas.

    En el menú lateral de Grafana, ve a Dashboards.

    Haz clic en el botón superior derecho New y selecciona Import.

    En la caja "Import via grafana.com", introduce el número 10990 (para RabbitMQ) y dale a Load.

    En el desplegable de la parte inferior, selecciona tu base de datos de Prometheus de Grafana Cloud y haz clic en Import.
