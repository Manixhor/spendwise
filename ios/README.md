# SpendWise for iPhone

Open `SpendWise.xcodeproj` in Xcode with the iOS SDK installed. Choose your Apple team in **Signing & Capabilities**, select a connected iPhone, and run **SpendWise**. The target supports iOS 17 and later. The app uses the existing production SpendWise site and its email and password sign-in.

Touch and hold the installed icon to try **Quick Add Expense**, **Repeat Last Expense**, and **Open Dashboard**. Test each action both after quitting the app and while it is in the background. Quick Add and Repeat open editable forms. Repeat uses the latest regular expense once the matching web backend is deployed, and opens a blank Quick Add form if there is no eligible expense.

The Safari web app still has a separate Quick Add Home Screen icon. The iOS project uses UIKit for the menu under the main app icon.
