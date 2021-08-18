# linkedGAN
GAN-generated profile images for LinkedIn.

## What is this?
This is a simple Python script to retrieve GAN-generated images from [This Person Does Not Exist](https://thispersondoesnotexist.com) and display them as your LinkedIn profile image. I currently run it as an AWS Lambda function at 1 minute intervals.

## Why?
1. For fun.
2. To make a point about how recruiting people based on their LinkedIn profile images harms diversity in the workplace.
3. To raise awareness of GAN-generated images being used by [spies](https://www.theverge.com/2019/6/13/18677341/ai-generated-fake-faces-spy-linked-in-contacts-associated-press) and [scammers](https://twitter.com/peteskomoroch/status/1360874312681496585).

## How does it work?
LinkedIn restricts their Profile Edit API to a small number of app partners, so this script works more like a bot, submitting requests to their AJAX API. Rather than use an API key it has to re-use cookies from an authenticated session (stored as a SecureString in AWS Systems Manager Parameter Store). At some point I'll add the ability to refresh cookies.

Steps:
1. Retrieve image from https://thispersondoesnotexist.com
2. Re-size and overlay with a watermark.
3. Register media upload metadata with Linkedin.
4. Upload files.
5. Switch profile images to the new media files.
