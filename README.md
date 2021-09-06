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
2. Re-size and overlay with a watermark (to make it obvious that it's an artificial image).
3. Register media upload metadata with Linkedin.
4. Upload files.
5. Switch profile images to the new media files.

## Warning!
I don't believe this is in breach of LinkedIn's terms of service because:
1. Automation isn't being used to message or otherwise interact with other LinkedIn members or scrape data from the site.
2. No misrepresentation is taking place, since the images are clearly labelled as being artificially generated.
3. This script generates a relatively small amount of traffic (the profile images are ~25KB) so as long as it doesn't get triggered too often it won't have any QoS impact.

However: this script is provided for interest only and is used entirely at your own risk.
