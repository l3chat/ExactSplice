# ExactSplice

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Українська](README.uk.md)

**Montage vidéo à l’image près avec un réencodage minimal.**

ExactSplice est un éditeur vidéo libre et local basé sur FFmpeg. Initialement nommé Video Hide, il permet de masquer des passages confidentiels d’enregistrements. Le navigateur et le serveur Python fonctionnent sur le même appareil, sans service cloud.

## État du projet

La version de référence est [Video Hide v0.3.1](https://github.com/l3chat/ExactSplice/releases/tag/v0.3.1). L’éditeur étendu 0.4 est en développement. Des versions portables Windows, Linux et macOS sont prévues, mais indisponibles pour le moment.

## Installation

Sous Android, installer Termux puis exécuter les commandes ci-dessous. Sous Linux, installer Python 3 et FFmpeg (avec ffprobe, libx264 et drawtext), cloner le dépôt et lancer le serveur.

### Android / Termux

```sh
pkg install python ffmpeg git
termux-setup-storage
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python gui.py
```

### Linux

```sh
git clone --branch v0.3.1 https://github.com/l3chat/ExactSplice.git
cd ExactSplice
python3 gui.py /path/to/videos
```

Ouvrir http://127.0.0.1:8765 dans le navigateur. L’ancienne interface est actuellement en russe. Le chemin du dossier vidéo peut être fourni en argument.

## Utilisation

1. Choisir une vidéo ; la lecture dépend des codecs pris en charge par le navigateur.
2. Pour les modes Smart, rechercher les images clés. Définir les bornes à l’aide de la timeline zoomable, de la navigation par images clés et du pas image par image.
3. Ajouter chaque intervalle. Les intervalles contigus ou superposés sont fusionnés ; une sélection valide non encore ajoutée est également exportée.
4. Régler les couleurs du fond et du compteur ainsi que sa taille, puis activer l’aperçu. L’export contient le compte à rebours, pas le texte de l’aperçu.
5. Enregistrer ou rouvrir le projet JSON : il contient les chemins et réglages, pas les vidéos. Les projets 0.2 sont importables ; choisir Smart Exact manuellement si nécessaire.
6. Choisir le mode, le traitement audio, le CRF et un nouveau nom MP4. Suivre la progression et le journal ; laisser le serveur actif jusqu’à la fin.

## Modes d’export

- **Full :** réencode toute la vidéo en H.264 ; CRF 18 par défaut.
- **Smart :** étend les intervalles vers les images clés existantes et copie les GOP non concernés sans réencodage.
- **Smart Exact (expérimental) :** réencode uniquement les GOP concernés, masque selon le numéro d’image et crée des images IDR aux bornes internes. Les autres GOP sont copiés. Une borne entre deux images est arrondie à l’image de présentation suivante ; le compteur indique la fin réelle du masquage.

## Compatibilité et confidentialité

Smart exige du H.264 yuv420p ordinaire, une fréquence d’images constante (CFR), des pixels carrés, un début à zéro et des images clés internes appropriées de part et d’autre des intervalles. Sinon, utiliser Full. Le nombre de paquets, les horodatages de présentation et les images décodées près des raccords sont vérifiés ; un échec empêche la publication. La vérification intégrale facultative compare les images décodées aux segments préparés ; en mode Full elle contrôle seulement le décodage. Ces contrôles ne garantissent pas la confidentialité : regarder chaque intervalle masqué et écouter le résultat avant partage.

Seule la première piste audio est conservée. La mise en sourdine la réencode en AAC avec une marge de 0,25 s de chaque côté ; vérifier le résultat. Les sous-titres, chapitres et métadonnées d’origine ne sont pas copiés. Les sources restent intactes. La taille finale n’est pas garantie ; les estimations ignorent les variations de débit et les nouvelles données.

## Progression et annulation

La progression est approximative : étape, vitesse FFmpeg, temps écoulé et restant estimé, volume de données de l’opération si disponible. La recherche d’images clés n’a pas de pourcentage précis. Le bouton d’arrêt envoie SIGTERM au groupe de processus ; l’annulation normale supprime les fichiers temporaires sans publier le résultat. Un arrêt forcé peut laisser des dossiers .video-hide-* contenant des images confidentielles près de la sortie. Ne les supprimer qu’après la fin du traitement.

## Tests et correction DTS

La version 0.3.1 normalise les DTS tout en conservant les PTS. Des tests réussis ont été rapportés sous Linux sur des vidéos synthétiques avec zéro, une ou deux images B, avec vérification Smart Exact et annulation. Un utilisateur a également confirmé le traitement d’un long enregistrement Zoom sous Android. Les tests étendus des appareils, codecs et du masquage audio restent à réaliser.

## Licence

Voir [LICENSE](LICENSE). FFmpeg et les autres dépendances ont leurs propres licences.
