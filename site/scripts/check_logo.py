from PIL import Image
img = Image.open('/root/projects/tenderlex/site/public/tenderlex-logo.png')
print('Size:', img.size, 'Mode:', img.mode)
