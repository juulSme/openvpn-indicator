# openvpn-indicator
## English
This indicator for Ubuntu Unity will help you !
It displays an icon changing on openvpn status. You can now start, stop and restart your openvpn service with a simple click and watch its status on your screen.

To add this indicator works on login, just type Startup Applications on the dash and choose the application with this name. Then, click "Add" on the right side of the little window just opened and fill the form in : 
  - Name : (whatever you want) Openvpn-Indicator
  - Command : python pathToYourPyFile/openvpn-indicator.py
  - Comment : (whatever you want again) Shortcut to openvpn informations

## French
Ceci est un indicateur pour le bureau Unity d'Ubuntu. Il ira se placer en haut à droite de votre bureau à côté de l'heure au démarrage de votre session (si vous le lui demandez gentiment).
Il affiche une icone représentant l'état dans lequel se trouve openvpn. Vous pourrez alors voir d'un coup d'oeil si vous êtes connecté et démarrer une connexion d'un clic (vous pourrez aussi l'arrêter et le relancer au besoin).

Pour lancer le script python rien de plus simple, aller dans la console dans le dossier de votre script (<code>cd le_chemin_du_dossier</code>) et lancer la commande suivante :
<pre><code>python openvpn-indicator.py &</code></pre>

Pour l'ajouter en démarrage automatique, entrez dans le Dash "Applications au démarrage" et choisissez l'application portant ce nom, une petite fenêtre s'ouvre dans laquelle 3 boutons sont disponibles sur la droite, choisissez "Ajouter" et remplissez le petit formulaire qui s'affiche :
  - Nom : (ce que vous voulez) Openvpn-Indicator
  - Commande : python cheminVersVotreFichierPython/openvpn-indicator.py
  - Commentaire : (ce que vous voulez) Raccourcis vers openvpn-indicator
