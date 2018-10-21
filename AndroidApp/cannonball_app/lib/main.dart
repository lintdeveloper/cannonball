import 'package:flutter/material.dart';
import 'package:cannonball_app/screens/sign_in_form.dart';

void main() => runApp(Cannonball());

class Cannonball extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
        title: 'Cannonball',
        home: Scaffold(
          appBar: AppBar(
            title: Text('Check In App'),
          ),
          body: Center(
            child: SignInForm(),
          ),
        )
    );
  }
}
